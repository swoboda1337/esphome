#ifdef USE_ESP32

#include "esphome/core/application.h"
#include "esphome/core/defines.h"
#include "preferences.h"
#include <esp_attr.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

void setup();  // NOLINT(readability-redundant-declaration)

// Weak stub for initArduino - overridden when the Arduino component is present.
// Name must match the Arduino framework's entry point, so the naming check is suppressed.
// NOLINTNEXTLINE(readability-identifier-naming)
extern "C" __attribute__((weak)) void initArduino() {}

namespace esphome {

// HAL functions live in hal.cpp. This file keeps only the loop task setup.
TaskHandle_t loop_task_handle = nullptr;  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)
// When the BSS segment is placed in PSRAM, keep the TCB and stack in internal
// RAM: FreeRTOS requires an internal TCB, and the loop task's stack must stay
// usable while the flash cache is disabled. DRAM_ATTR moves them into the
// loaded data segment, so apply it only when needed to avoid the flash cost.
#if CONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY
#define LOOP_TASK_MEM_ATTR DRAM_ATTR
#else
#define LOOP_TASK_MEM_ATTR
#endif
static LOOP_TASK_MEM_ATTR StaticTask_t loop_task_tcb;  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)
static LOOP_TASK_MEM_ATTR StackType_t
    loop_task_stack[ESPHOME_LOOP_TASK_STACK_SIZE];  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)

void loop_task(void *pv_params) {
  setup();
  while (true) {
    App.loop();
  }
}

extern "C" void app_main() {
  initArduino();
  esp32::setup_preferences();
#if CONFIG_FREERTOS_UNICORE
  loop_task_handle = xTaskCreateStatic(loop_task, "loopTask", ESPHOME_LOOP_TASK_STACK_SIZE, nullptr, 1, loop_task_stack,
                                       &loop_task_tcb);
#else
  loop_task_handle = xTaskCreateStaticPinnedToCore(loop_task, "loopTask", ESPHOME_LOOP_TASK_STACK_SIZE, nullptr, 1,
                                                   loop_task_stack, &loop_task_tcb, 1);
#endif
}

}  // namespace esphome

#endif  // USE_ESP32
