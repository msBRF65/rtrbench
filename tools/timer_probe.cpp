#include "loop_timer.hpp"
#include <chrono>
#include <cstring>
#include <thread>

int main(int argc, char** argv) {
    if (argc > 1 && std::strcmp(argv[1], "invalid") == 0) {
        RTRBENCH_ROI_END(); // Mispaired boundaries must fail rather than emit misleading data.
        return 0;
    }
    RTRBENCH_ROI_BEGIN();
    if (argc > 1 && std::strcmp(argv[1], "overhead") == 0) {
        for (int i = 0; i < 100000; ++i) {
            RTRBENCH_LOOP("Empty scope");
            asm volatile("" ::: "memory");
        }
    } else {
        {
            RTRBENCH_LOOP("Parent");
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
            {
                RTRBENCH_LOOP("Child");
                std::this_thread::sleep_for(std::chrono::milliseconds(80));
            }
            RTRBENCH_ROI_END();
            std::this_thread::sleep_for(std::chrono::milliseconds(300));
            RTRBENCH_ROI_BEGIN();
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    RTRBENCH_ROI_END();
}
