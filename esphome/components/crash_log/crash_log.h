#pragma once

#include "esphome/core/component.h"

#ifndef CRASH_LOG_BUFFER_SIZE
#define CRASH_LOG_BUFFER_SIZE 4096
#endif

namespace esphome::crash_log {

// Magic value to validate buffer contents survived reset
static constexpr uint32_t CRASH_LOG_MAGIC = 0xC2A5A10C;

// Structure stored in noinit RAM - survives warm resets
struct CrashLogBuffer {
  uint32_t magic;                           // Validation magic
  uint32_t write_index;                     // Current write position (circular)
  uint32_t reset_count;                     // Number of resets with valid data
  uint32_t fault_reason;                    // Fault reason code if crashed
  uint32_t fault_pc;                        // Program counter at fault
  uint32_t fault_lr;                        // Link register at fault
  char buffer[CRASH_LOG_BUFFER_SIZE - 24];  // Log buffer (size - header)
};

class CrashLog : public Component {
 public:
  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::BUS; }

  void set_buffer_size(size_t size) { this->buffer_size_ = size; }
  void set_dump_at_boot(bool dump) { this->dump_at_boot_ = dump; }

  // Write to the crash log buffer (called from logger hook)
  void write(const char *msg, size_t len);

  // Check if there's crash data from previous boot
  bool has_crash_data() const;

  // Get the crash log from previous boot
  const char *get_crash_log() const;

  // Clear the crash log
  void clear();

  // Store fault information (called from fault handler)
  void store_fault(uint32_t reason, uint32_t pc, uint32_t lr);

 protected:
  size_t buffer_size_{CRASH_LOG_BUFFER_SIZE};
  bool dump_at_boot_{true};
  bool had_crash_data_{false};
};

// Global instance for fault handler access
extern CrashLog *global_crash_log;  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)

}  // namespace esphome::crash_log
