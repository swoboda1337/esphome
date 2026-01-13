#ifdef USE_ZEPHYR

#include "esphome/core/application.h"
#include "esphome/core/log.h"
#include "logger.h"

#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/linker/section_tags.h>
#include <zephyr/sys/printk.h>
#include <zephyr/usb/usb_device.h>
#ifdef USE_LOGGER_EARLY_MESSAGE
#include <zephyr/drivers/hwinfo.h>
#endif

namespace esphome::zephyr_coredump {

__attribute__((weak)) void print_coredump() {}

}  // namespace esphome::zephyr_coredump

namespace esphome::logger {

static const char *const TAG = "logger";

// Noinit ring buffer for crash debugging - survives soft resets
static constexpr uint32_t NOINIT_LOG_MAGIC = 0xDEADBEEF;
static constexpr size_t NOINIT_LOG_LINES = 16;
static constexpr size_t NOINIT_LOG_LINE_LEN = 128;

struct NoInitLogBuffer {
  uint32_t magic;
  uint32_t write_index;
  uint32_t count;
  char lines[NOINIT_LOG_LINES][NOINIT_LOG_LINE_LEN];
};

// Place in noinit section - survives resets but not power cycles
static __noinit NoInitLogBuffer noinit_log;

// Flag to freeze buffer until dumped (prevents new logs overwriting crash logs)
static bool noinit_log_frozen = false;
static bool noinit_log_initialized = false;

void noinit_log_init() {
  if (noinit_log_initialized) {
    return;
  }
  noinit_log_initialized = true;

  // If buffer has valid data from before reset, freeze it until dumped
  if (noinit_log.magic == NOINIT_LOG_MAGIC && noinit_log.count > 0) {
    noinit_log_frozen = true;
  } else {
    // First boot or power cycle - initialize
    noinit_log.magic = NOINIT_LOG_MAGIC;
    noinit_log.write_index = 0;
    noinit_log.count = 0;
    noinit_log_frozen = false;
  }
}

void noinit_log_add(const char *msg, size_t len) {
  // Initialize on first call (before pre_setup runs)
  if (!noinit_log_initialized) {
    noinit_log_init();
  }

  // Don't add if frozen (waiting for dump)
  if (noinit_log_frozen) {
    return;
  }

  // Copy message to current slot, truncating if needed
  size_t copy_len = (len < NOINIT_LOG_LINE_LEN - 1) ? len : (NOINIT_LOG_LINE_LEN - 1);
  memcpy(noinit_log.lines[noinit_log.write_index], msg, copy_len);
  noinit_log.lines[noinit_log.write_index][copy_len] = '\0';

  // Strip trailing newline if present
  if (copy_len > 0 && noinit_log.lines[noinit_log.write_index][copy_len - 1] == '\n') {
    noinit_log.lines[noinit_log.write_index][copy_len - 1] = '\0';
  }

  // Advance ring buffer
  noinit_log.write_index = (noinit_log.write_index + 1) % NOINIT_LOG_LINES;
  if (noinit_log.count < NOINIT_LOG_LINES) {
    noinit_log.count++;
  }
}

bool noinit_log_has_data() { return noinit_log.magic == NOINIT_LOG_MAGIC && noinit_log.count > 0; }

void noinit_log_dump(const device *uart_dev) {
  if (!noinit_log_has_data() || uart_dev == nullptr) {
    return;
  }

  // Print header
  const char *header = "\r\n=== LAST LOG BEFORE RESET ===\r\n";
  for (const char *p = header; *p; p++) {
    uart_poll_out(uart_dev, *p);
  }

  // Calculate start index for oldest message
  uint32_t start_idx;
  if (noinit_log.count < NOINIT_LOG_LINES) {
    start_idx = 0;
  } else {
    start_idx = noinit_log.write_index;  // Oldest is at write_index when full
  }

  // Dump messages in order (oldest to newest)
  for (uint32_t i = 0; i < noinit_log.count; i++) {
    uint32_t idx = (start_idx + i) % NOINIT_LOG_LINES;
    const char *line = noinit_log.lines[idx];
    for (const char *p = line; *p; p++) {
      uart_poll_out(uart_dev, *p);
    }
    uart_poll_out(uart_dev, '\r');
    uart_poll_out(uart_dev, '\n');
  }

  // Print footer
  const char *footer = "=== END LAST LOG ===\r\n\r\n";
  for (const char *p = footer; *p; p++) {
    uart_poll_out(uart_dev, *p);
  }
}

void noinit_log_clear() {
  noinit_log.count = 0;
  noinit_log.write_index = 0;
  noinit_log_frozen = false;  // Unfreeze so new logs can be written
}

#ifdef USE_LOGGER_USB_CDC
static bool noinit_dumped = false;

static void uart_print(const device *uart_dev, const char *str) {
  for (const char *p = str; *p; p++) {
    uart_poll_out(uart_dev, *p);
  }
}

void Logger::loop() {
  if (this->uart_ != UART_SELECTION_USB_CDC || this->uart_dev_ == nullptr) {
    return;
  }
  static bool opened = false;
  uint32_t dtr = 0;
  uart_line_ctrl_get(this->uart_dev_, UART_LINE_CTRL_DTR, &dtr);

  /* Poll if the DTR flag was set, optional */
  if (opened == dtr) {
    return;
  }

  if (!opened) {
    // CDC just connected - dump noinit logs
    if (!noinit_dumped) {
      char buf[64];
      snprintf(buf, sizeof(buf), "\r\n[NOINIT] magic=0x%08X count=%u idx=%u\r\n", (unsigned) noinit_log.magic,
               (unsigned) noinit_log.count, (unsigned) noinit_log.write_index);
      uart_print(this->uart_dev_, buf);

      if (noinit_log_has_data()) {
        noinit_log_dump(this->uart_dev_);
      } else {
        uart_print(this->uart_dev_, "[NOINIT] No data in buffer\r\n");
      }
      noinit_log_clear();
      noinit_dumped = true;
    }
    App.schedule_dump_config();
  }
  opened = !opened;
}
#endif

void Logger::pre_setup() {
  if (this->baud_rate_ > 0) {
    static const struct device *uart_dev = nullptr;
    switch (this->uart_) {
      case UART_SELECTION_UART0:
        uart_dev = DEVICE_DT_GET_OR_NULL(DT_NODELABEL(uart0));
        break;
      case UART_SELECTION_UART1:
        uart_dev = DEVICE_DT_GET_OR_NULL(DT_NODELABEL(uart1));
        break;
#ifdef USE_LOGGER_USB_CDC
      case UART_SELECTION_USB_CDC:
        uart_dev = DEVICE_DT_GET_OR_NULL(DT_NODELABEL(cdc_acm_uart0));
        if (device_is_ready(uart_dev)) {
          usb_enable(nullptr);
        }
        break;
#endif
    }
    if (!device_is_ready(uart_dev)) {
      ESP_LOGE(TAG, "%s is not ready.", LOG_STR_ARG(get_uart_selection_()));
    } else {
      this->uart_dev_ = uart_dev;
#ifdef USE_LOGGER_WAIT_FOR_CDC
      uint32_t dtr = 0;
      uint32_t count = (10 * 100);  // wait 10 sec for USB CDC to have early logs
      while (dtr == 0 && count-- != 0) {
        uart_line_ctrl_get(this->uart_dev_, UART_LINE_CTRL_DTR, &dtr);
        delay(10);
        arch_feed_wdt();
      }
#endif
    }
  }

  // For non-CDC UARTs, dump noinit logs immediately (CDC dumps in loop when connected)
#ifndef USE_LOGGER_USB_CDC
  if (this->uart_dev_ != nullptr) {
    noinit_log_dump(this->uart_dev_);
    noinit_log_clear();
  }
#else
  if (this->uart_ != UART_SELECTION_USB_CDC && this->uart_dev_ != nullptr) {
    noinit_log_dump(this->uart_dev_);
    noinit_log_clear();
  }
#endif

  // Initialize noinit log buffer for this session
  noinit_log_init();

  global_logger = this;
  ESP_LOGI(TAG, "Log initialized");
#ifdef USE_LOGGER_EARLY_MESSAGE
  uint32_t cause;
  if (hwinfo_get_reset_cause(&cause) == 0) {
    ESP_LOGI(TAG, "boot reason %u", cause);
  }
  zephyr_coredump::print_coredump();
#endif
}

void HOT Logger::write_msg_(const char *msg, size_t len) {
  // Store in noinit buffer for crash debugging
  noinit_log_add(msg, len);

  // Single write with newline already in buffer (added by caller)
#ifdef CONFIG_PRINTK
  // Requires the debug component and an active SWD connection.
  // It is used for pyocd rtt -t nrf52840
  k_str_out(const_cast<char *>(msg), len);
#endif
  if (this->uart_dev_ == nullptr) {
    return;
  }
  for (size_t i = 0; i < len; ++i) {
    uart_poll_out(this->uart_dev_, msg[i]);
  }
}

const LogString *Logger::get_uart_selection_() {
  switch (this->uart_) {
    case UART_SELECTION_UART0:
      return LOG_STR("UART0");
    case UART_SELECTION_UART1:
      return LOG_STR("UART1");
#ifdef USE_LOGGER_USB_CDC
    case UART_SELECTION_USB_CDC:
      return LOG_STR("USB_CDC");
#endif
    default:
      return LOG_STR("UNKNOWN");
  }
}

}  // namespace esphome::logger

#endif
