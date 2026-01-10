#ifdef USE_ZEPHYR

#include "crash_log.h"
#include "esphome/core/log.h"
#include "esphome/core/hal.h"
#include "esphome/components/logger/logger.h"

#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>
#include <cstring>

namespace esphome::crash_log {

static const char *const TAG = "crash_log";

// Place buffer in .noinit section - RAM that isn't cleared on reset
// This survives warm resets (watchdog, software reset) but not power cycles
static CrashLogBuffer __noinit crash_buffer_;

CrashLog *global_crash_log = nullptr;   // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)
static bool crash_log_enabled_ = true;  // NOLINT - can disable during dump
static bool auto_init_ran_ = false;     // NOLINT - debug flag

void CrashLog::setup() {
  // Disable writing while we dump
  crash_log_enabled_ = false;

  size_t buffer_size = sizeof(crash_buffer_.buffer);

  // Debug: show raw buffer state at boot
  ESP_LOGW(TAG, "Boot state: magic=0x%08x (want 0x%08x) reset_count=%u write_index=%u auto_init=%s",
           crash_buffer_.magic, CRASH_LOG_MAGIC, crash_buffer_.reset_count, crash_buffer_.write_index,
           auto_init_ran_ ? "YES" : "NO");

  // Check if buffer contains valid data from previous boot
  // Magic + reset_count > 0 means this is preserved data from a previous boot
  // (auto-init sets reset_count = 0, setup() sets it to 1 at end)
  if (crash_buffer_.magic == CRASH_LOG_MAGIC && crash_buffer_.reset_count > 0 && crash_buffer_.write_index > 0) {
    // This is data from a previous boot
    this->had_crash_data_ = true;
    uint32_t reset_count = crash_buffer_.reset_count;
    size_t saved_write_index = crash_buffer_.write_index;

    // Calculate actual data length and start position for circular buffer
    size_t data_len;
    size_t start_idx;
    if (saved_write_index >= buffer_size) {
      // Buffer wrapped - read from write position (oldest) to write position (newest)
      data_len = buffer_size;
      start_idx = saved_write_index % buffer_size;
    } else {
      // Buffer didn't wrap - read from start
      data_len = saved_write_index;
      start_idx = 0;
    }

    if (this->dump_at_boot_ && data_len > 0 && logger::global_logger != nullptr) {
      ESP_LOGW(TAG, "=== Crash log from previous boot (reset #%u, %u bytes) ===", reset_count, (unsigned) data_len);

      if (crash_buffer_.fault_reason != 0) {
        ESP_LOGW(TAG, "Fault: reason=0x%08x PC=0x%08x LR=0x%08x", crash_buffer_.fault_reason, crash_buffer_.fault_pc,
                 crash_buffer_.fault_lr);
      }

      // Dump buffer directly, handling circular wrap
      if (start_idx == 0) {
        // Buffer didn't wrap - single contiguous write
        logger::global_logger->write_raw(crash_buffer_.buffer, data_len);
      } else {
        // Buffer wrapped - write in two parts
        // Part 1: from start_idx to end of buffer (oldest data)
        logger::global_logger->write_raw(&crash_buffer_.buffer[start_idx], buffer_size - start_idx);
        // Part 2: from start of buffer to start_idx (newest data)
        logger::global_logger->write_raw(crash_buffer_.buffer, start_idx);
      }

      ESP_LOGW(TAG, "=== End crash log ===");
    }
  }

  // Initialize/reset buffer for this boot session
  crash_buffer_.magic = CRASH_LOG_MAGIC;
  // Set reset_count to 1 so next boot knows there's previous data
  // (auto-init sets it to 0, so reset_count > 0 means setup() completed on previous boot)
  crash_buffer_.reset_count = this->had_crash_data_ ? crash_buffer_.reset_count + 1 : 1;
  crash_buffer_.write_index = 0;
  crash_buffer_.fault_reason = 0;
  crash_buffer_.fault_pc = 0;
  crash_buffer_.fault_lr = 0;
  memset(crash_buffer_.buffer, 0, sizeof(crash_buffer_.buffer));

  // NOW enable logging to crash buffer
  global_crash_log = this;
  crash_log_enabled_ = true;

  ESP_LOGD(TAG, "Crash log initialized, buffer size: %u bytes", sizeof(crash_buffer_.buffer));
}

void CrashLog::dump_config() {
  ESP_LOGCONFIG(TAG, "Crash Log:");
  ESP_LOGCONFIG(TAG, "  Buffer size: %u bytes", sizeof(crash_buffer_.buffer));
  ESP_LOGCONFIG(TAG, "  Dump at boot: %s", YESNO(this->dump_at_boot_));
  ESP_LOGCONFIG(TAG, "  Had crash data: %s", YESNO(this->had_crash_data_));
  ESP_LOGCONFIG(TAG, "  Reset count: %u", crash_buffer_.reset_count);
}

void CrashLog::write(const char *msg, size_t len) {
  if (msg == nullptr || len == 0) {
    return;
  }

  size_t buffer_size = sizeof(crash_buffer_.buffer);
  size_t write_idx = crash_buffer_.write_index;

  for (size_t i = 0; i < len; i++) {
    crash_buffer_.buffer[write_idx % buffer_size] = msg[i];
    write_idx++;
  }

  crash_buffer_.write_index = write_idx;
}

bool CrashLog::has_crash_data() const { return this->had_crash_data_; }

const char *CrashLog::get_crash_log() const {
  if (!this->had_crash_data_) {
    return nullptr;
  }
  return crash_buffer_.buffer;
}

void CrashLog::clear() {
  crash_buffer_.write_index = 0;
  crash_buffer_.fault_reason = 0;
  crash_buffer_.fault_pc = 0;
  crash_buffer_.fault_lr = 0;
  memset(crash_buffer_.buffer, 0, sizeof(crash_buffer_.buffer));
}

void CrashLog::store_fault(uint32_t reason, uint32_t pc, uint32_t lr) {
  crash_buffer_.fault_reason = reason;
  crash_buffer_.fault_pc = pc;
  crash_buffer_.fault_lr = lr;
}

}  // namespace esphome::crash_log

// Direct buffer write - works even before component setup
static void write_to_buffer(const char *msg, size_t len) {
  using namespace esphome::crash_log;

  if (msg == nullptr || len == 0 || !crash_log_enabled_) {
    return;
  }

  // Auto-initialize buffer if needed (first log before setup, or after power cycle)
  // This only runs if magic doesn't match, meaning no valid previous data exists
  if (crash_buffer_.magic != CRASH_LOG_MAGIC) {
    // Debug: this means .noinit was NOT preserved (power cycle or first flash)
    auto_init_ran_ = true;
    crash_buffer_.magic = CRASH_LOG_MAGIC;
    crash_buffer_.write_index = 0;
    crash_buffer_.reset_count = 0;
    crash_buffer_.fault_reason = 0;
    crash_buffer_.fault_pc = 0;
    crash_buffer_.fault_lr = 0;
  }

  size_t buffer_size = sizeof(crash_buffer_.buffer);
  size_t write_idx = crash_buffer_.write_index;

  for (size_t i = 0; i < len; i++) {
    crash_buffer_.buffer[write_idx % buffer_size] = msg[i];
    write_idx++;
  }

  crash_buffer_.write_index = write_idx;
}

// C linkage wrapper for logger integration
extern "C" void crash_log_write(const char *msg, size_t len) {
  using namespace esphome::crash_log;
  // Write directly to buffer - works before and after setup
  // Skip if we're currently dumping (global_crash_log temporarily null during dump)
  write_to_buffer(msg, len);
}

// TODO: Add fault handler hook to capture PC/LR on crash
// The Zephyr API varies by version, so leaving this out for now.
// The log buffer will still capture logs leading up to a crash.

#endif  // USE_ZEPHYR
