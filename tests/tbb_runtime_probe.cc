#include <oneapi/tbb/global_control.h>
#include <oneapi/tbb/parallel_for.h>
#include <oneapi/tbb/blocked_range.h>
#include <oneapi/tbb/task_group.h>
#include <cassert>
#include <atomic>
#include <cstdio>
#include <mutex>
#include <set>
#include <thread>
#include <vector>
int main() {
  oneapi::tbb::global_control control(oneapi::tbb::global_control::max_allowed_parallelism,2);
  std::vector<unsigned> values(4096);
  std::mutex lock;std::set<std::thread::id> threads;
  for (unsigned iteration=0;iteration<3;iteration++) {
    oneapi::tbb::parallel_for(oneapi::tbb::blocked_range<unsigned>(0,values.size(),16),[&](auto range){
      {std::lock_guard<std::mutex> guard(lock);threads.insert(std::this_thread::get_id());}
      for(unsigned index=range.begin();index<range.end();index++) {
        unsigned value=index+iteration;
        for(unsigned step=0;step<20000;step++) value=value*1664525u+1013904223u;
        values[index]=value;
      }
    });
    for(unsigned index=0;index<values.size();index++) {
      unsigned expected=index+iteration;
      for(unsigned step=0;step<20000;step++) expected=expected*1664525u+1013904223u;
      assert(values[index]==expected);
    }
  }
  assert(threads.size()==2);
  std::atomic<unsigned> completed{0};oneapi::tbb::task_group group;
  for(unsigned index=0;index<64;index++) group.run([&]{completed.fetch_add(1);});
  group.wait();assert(completed.load()==64);
  std::puts("PASS: real oneTBB tasks, repeated parallel results and two execution threads.");
}
