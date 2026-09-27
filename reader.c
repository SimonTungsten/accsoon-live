// Accsoon CineView SE 4K async USB reader with ordered emission.
// Many transfers in flight keep the endpoint serviced (a synchronous read loop
// drops data), but libusb completion order is not guaranteed, so each transfer
// is tagged at submission time and emitted strictly in that order.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
#include <libusb.h>

#define VID 0x3561
#define PID 0x0064
#define EP_IN  0x81
#define EP_OUT 0x02
#define NXFER 32
#define XLEN  65536
#define RING  512

static libusb_device_handle *h;
static volatile int running = 1;
static unsigned long long submitted = 0, next_emit = 0, count = 0, total = 0, reordered = 0;

typedef struct { unsigned char *data; int len; int ready; } slot_t;
static slot_t ring[RING];
static unsigned long long tag_of[NXFER];

static const unsigned char CONN1[] = {
  0xc6,0xea,0x85,0x78,0x01,0x00,0x0e,0x00,0x93,0x6e,0x77,0x78,
  0x78,0x56,0x34,0x12,0x40,0x00,0x0b,0x00,0x01,0x00 };

static void *keepalive(void *a) {
  (void)a; int n;
  while (running) {
    libusb_bulk_transfer(h, EP_OUT, (unsigned char *)CONN1, sizeof CONN1, &n, 500);
    usleep(400000);
  }
  return NULL;
}

static void drain(void) {
  while (ring[next_emit % RING].ready) {
    slot_t *s = &ring[next_emit % RING];
    unsigned int len = (unsigned int)s->len;
    if (len) { fwrite(&len, 4, 1, stdout); fwrite(s->data, 1, len, stdout); }
    free(s->data); s->data = NULL; s->ready = 0;
    total += len; count++; next_emit++;
  }
}

static void LIBUSB_CALL cb(struct libusb_transfer *t) {
  long idx = (long)t->user_data;
  unsigned long long tag = tag_of[idx];
  slot_t *s = &ring[tag % RING];
  if (t->status == LIBUSB_TRANSFER_COMPLETED && t->actual_length > 0) {
    s->data = malloc(t->actual_length);
    memcpy(s->data, t->buffer, t->actual_length);
    s->len = t->actual_length;
  } else { s->data = NULL; s->len = 0; }
  s->ready = 1;
  if (tag != next_emit) reordered++;
  drain();
  if (running) { tag_of[idx] = submitted++; libusb_submit_transfer(t); }
}

int main(int argc, char **argv) {
  int seconds = argc > 1 ? atoi(argv[1]) : 0;
  if (libusb_init(NULL) < 0) { fprintf(stderr, "libusb_init failed\n"); return 1; }
  h = libusb_open_device_with_vid_pid(NULL, VID, PID);
  if (!h) { fprintf(stderr, "device not found\n"); return 1; }
  libusb_set_auto_detach_kernel_driver(h, 1);
  if (libusb_claim_interface(h, 0) < 0) { fprintf(stderr, "claim failed\n"); return 1; }
  pthread_t th; pthread_create(&th, NULL, keepalive, NULL);

  struct libusb_transfer *xs[NXFER];
  for (long i = 0; i < NXFER; i++) {
    xs[i] = libusb_alloc_transfer(0);
    unsigned char *buf = malloc(XLEN);
    libusb_fill_bulk_transfer(xs[i], h, EP_IN, buf, XLEN, cb, (void *)i, 0);
    tag_of[i] = submitted++;
    libusb_submit_transfer(xs[i]);
  }
  struct timeval tv = { 0, 50000 };
  time_t t0 = time(NULL);
  while (running) {
    libusb_handle_events_timeout_completed(NULL, &tv, NULL);
    if (seconds && time(NULL) - t0 >= seconds) running = 0;
  }
  fflush(stdout);
  fprintf(stderr, "transfers=%llu bytes=%llu out-of-order=%llu\n", count, total, reordered);
  libusb_release_interface(h, 0); libusb_close(h); libusb_exit(NULL);
  return 0;
}
