#pragma once

#include "esphome/core/component.h"
#include "esphome/core/gpio.h"
#include "esphome/components/sensor/sensor.h"

#include <cinttypes>

namespace esphome {
namespace ultrasonic {

class UltrasonicSensorComponent : public sensor::Sensor, public PollingComponent {
 public:
  void set_trigger_pin(InternalGPIOPin *trigger_pin) { this->trigger_pin_ = trigger_pin; }
  void set_echo_pin(InternalGPIOPin *echo_pin) { this->echo_pin_ = echo_pin; }

  /// Set the timeout for waiting for the echo in µs.
  void set_timeout_us(uint32_t timeout_us) { this->timeout_us_ = timeout_us; }

  /// Set the time in µs the trigger pin should be enabled for in µs, defaults to 10µs (for HC-SR04)
  void set_pulse_time_us(uint32_t pulse_time_us) { this->pulse_time_us_ = pulse_time_us; }

  void setup() override;
  void dump_config() override;
  void update() override;
  float get_setup_priority() const override;

 protected:
  struct MeasureResult {
    uint32_t start;
    uint32_t pulse_start;
    uint32_t pulse_end;
  };

  /// Helper function to convert the specified echo duration in µs to meters.
  static float us_to_m(uint32_t us);

  /// Perform the measurement with interrupts disabled. Must be in IRAM to avoid flash access delays.
  MeasureResult measure_();

  InternalGPIOPin *trigger_pin_;
  InternalGPIOPin *echo_pin_;
  ISRInternalGPIOPin trigger_isr_;
  ISRInternalGPIOPin echo_isr_;
  uint32_t timeout_us_{};
  uint32_t pulse_time_us_{};
};

}  // namespace ultrasonic
}  // namespace esphome
