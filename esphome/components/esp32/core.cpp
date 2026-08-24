#ifdef USE_ESP32

#include "esphome/core/application.h"
#include "esphome/core/defines.h"
#include "preferences.h"
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

#if !CONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY
static StaticTask_t loop_task_tcb;  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)
static StackType_t
    loop_task_stack[ESPHOME_LOOP_TASK_STACK_SIZE];  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)
#endif

void loop_task(void *pv_params) {
  setup();
  while (true) {
    App.loop();
  }
}

extern "C" void app_main() {
  initArduino();
  esp32::setup_preferences();
#if CONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY
  // With the BSS segment in PSRAM, static globals would place the TCB and
  // stack in external RAM and the first task creation would assert before
  // the logger exists. Let FreeRTOS allocate them instead: its allocator is
  // fixed to internal RAM.
#if CONFIG_FREERTOS_UNICORE
  xTaskCreate(loop_task, "loopTask", ESPHOME_LOOP_TASK_STACK_SIZE, nullptr, 1, &loop_task_handle);
#else
  xTaskCreatePinnedToCore(loop_task, "loopTask", ESPHOME_LOOP_TASK_STACK_SIZE, nullptr, 1, &loop_task_handle, 1);
#endif
#else
#if CONFIG_FREERTOS_UNICORE
  loop_task_handle = xTaskCreateStatic(loop_task, "loopTask", ESPHOME_LOOP_TASK_STACK_SIZE, nullptr, 1, loop_task_stack,
                                       &loop_task_tcb);
#else
  loop_task_handle = xTaskCreateStaticPinnedToCore(loop_task, "loopTask", ESPHOME_LOOP_TASK_STACK_SIZE, nullptr, 1,
                                                   loop_task_stack, &loop_task_tcb, 1);
#endif
#endif
}

}  // namespace esphome

#endif  // USE_ESP32
