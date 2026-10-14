#include <assert.h>
#include <stdio.h>
#include <emscripten.h>

int main(void)
{
  volatile int value = 0;
  for (int i = 0; i < 3; ++i) {
    value += 7;
    emscripten_sleep(1);
    assert(value == (i + 1) * 7);
  }
  printf("PASS: resumed exact state %d\n", value);
  return 0;
}
