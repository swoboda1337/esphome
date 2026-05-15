#include "pipsolar_output.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

namespace esphome::pipsolar {

static const char *const TAG = "pipsolar.output";

void PipsolarOutput::write_state(float state) {
  char tmp[16];
  snprintf(tmp, sizeof(tmp), this->set_command_, state);

  if (std::ranges::find(this->possible_values_, state) != this->possible_values_.end()) {
    ESP_LOGD(TAG, "Will write: %s out of value %f / %02.0f", tmp, state, state);
    this->parent_->queue_command(std::string(tmp));
  } else {
    ESP_LOGD(TAG, "Will not write: %s as it is not in list of allowed values", tmp);
  }
}
}  // namespace esphome::pipsolar
