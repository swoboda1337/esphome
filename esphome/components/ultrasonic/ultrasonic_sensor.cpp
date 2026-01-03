#include "ultrasonic_sensor.h"
#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

namespace esphome {
namespace ultrasonic {

static const char *const TAG = "ultrasonic.sensor";

void UltrasonicSensorComponent::setup() {
  this->trigger_pin_->setup();
  this->trigger_pin_->digital_write(false);
  this->trigger_isr_ = this->trigger_pin_->to_isr();
  this->echo_pin_->setup();
  this->echo_isr_ = this->echo_pin_->to_isr();
}

UltrasonicSensorComponent::MeasureResult IRAM_ATTR UltrasonicSensorComponent::measure_() {
  // Disable interrupts during the entire measurement to prevent WiFi stack
  // or other interrupts from disrupting the timing-critical polling loop.
  // Maximum lock duration is timeout_us_ + pulse_time_us_ (typically ~12-17ms for 2-3m range).
  InterruptLock lock;

  this->trigger_isr_.digital_write(true);
  delayMicroseconds(this->pulse_time_us_);
  this->trigger_isr_.digital_write(false);

  const uint32_t start = micros();
  // Wait for any previous echo to finish (pin HIGH)
  while (micros() - start < this->timeout_us_ && this->echo_isr_.digital_read())
    ;
  // Wait for echo pulse to start (pin goes HIGH)
  while (micros() - start < this->timeout_us_ && !this->echo_isr_.digital_read())
    ;
  const uint32_t pulse_start = micros();
  // Wait for echo pulse to end (pin goes LOW)
  while (micros() - start < this->timeout_us_ && this->echo_isr_.digital_read())
    ;
  const uint32_t pulse_end = micros();

  return {start, pulse_start, pulse_end};
}

void UltrasonicSensorComponent::update() {
  MeasureResult result = this->measure_();

  ESP_LOGD(TAG,
           "'%s' - timeout_us: %" PRIu32 ", pulse_time_us: %" PRIu32 ", start: %" PRIu32 ", pulse_start: %" PRIu32
           ", pulse_end: %" PRIu32,
           this->name_.c_str(), this->timeout_us_, this->pulse_time_us_, result.start, result.pulse_start,
           result.pulse_end);

  uint32_t pulse_us = result.pulse_end - result.pulse_start;
  bool timed_out = (result.pulse_end - result.start) >= this->timeout_us_;

  if (timed_out) {
    ESP_LOGD(TAG, "'%s' - Distance measurement timed out!", this->name_.c_str());
    this->publish_state(NAN);
  } else {
    float distance = UltrasonicSensorComponent::us_to_m(pulse_us);
    ESP_LOGD(TAG, "'%s' - Got distance: %.3f m (echo: %" PRIu32 "us)", this->name_.c_str(), distance, pulse_us);
    this->publish_state(distance);
  }
}
void UltrasonicSensorComponent::dump_config() {
  LOG_SENSOR("", "Ultrasonic Sensor", this);
  LOG_PIN("  Echo Pin: ", this->echo_pin_);
  LOG_PIN("  Trigger Pin: ", this->trigger_pin_);
  ESP_LOGCONFIG(TAG,
                "  Pulse time: %" PRIu32 " µs\n"
                "  Timeout: %" PRIu32 " µs",
                this->pulse_time_us_, this->timeout_us_);
  LOG_UPDATE_INTERVAL(this);
}
float UltrasonicSensorComponent::us_to_m(uint32_t us) {
  const float speed_sound_m_per_s = 343.0f;
  const float time_s = us / 1e6f;
  const float total_dist = time_s * speed_sound_m_per_s;
  return total_dist / 2.0f;
}
float UltrasonicSensorComponent::get_setup_priority() const { return setup_priority::DATA; }

}  // namespace ultrasonic
}  // namespace esphome
