#include "tca9548a.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace esphome {
namespace tca9548a {

static const char *const TAG = "tca9548a";

i2c::ErrorCode TCA9548AChannel::write_readv(uint8_t address, const uint8_t *write_buffer, size_t write_count,
                                            uint8_t *read_buffer, size_t read_count) {
  auto err = this->parent_->switch_to_channel(channel_);
  if (err != i2c::ERROR_OK)
    return err;
  return this->parent_->bus_->write_readv(address, write_buffer, write_count, read_buffer, read_count);
}
void TCA9548AComponent::setup() {
  uint8_t status = 0;
  if (this->read(&status, 1) != i2c::ERROR_OK) {
    ESP_LOGE(TAG, "TCA9548A failed");
    this->mark_failed();
    return;
  }
  ESP_LOGD(TAG, "Channels currently open: %d", status);
  if (status != 0) {
    this->current_channel_val_ = status;
    this->disable_all_channels();
  }
}
void TCA9548AComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "TCA9548A:");
  LOG_I2C_DEVICE(this);
}

i2c::ErrorCode TCA9548AComponent::switch_to_channel(uint8_t channel) {
  if (this->is_failed())
    return i2c::ERROR_NOT_INITIALIZED;

  uint8_t channel_val = 1 << channel;
  if (channel_val == this->current_channel_val_)
    return i2c::ERROR_OK;
  auto err = this->write(&channel_val, 1);
  if (err == i2c::ERROR_OK) {
    this->current_channel_val_ = channel_val;
    delay(1);
  }
  return err;
}

void TCA9548AComponent::disable_all_channels() {
  if (this->current_channel_val_ == 0)
    return;
  if (this->write(&TCA9548A_DISABLE_CHANNELS_COMMAND, 1) != i2c::ERROR_OK) {
    ESP_LOGE(TAG, "Failed to disable all channels.");
    this->status_set_error();  // couldn't disable channels, set error status
  }
  this->current_channel_val_ = 0;
}

}  // namespace tca9548a
}  // namespace esphome
