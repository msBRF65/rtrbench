#include "loop_timer.hpp"
#include <chrono>
#include <cstring>
#include <thread>

void outside_roi() {
    RTRBENCH_LOOP("Off-ROI helper");
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
}

template<typename T> void template_scope() {
    RTRBENCH_LOOP("Template callsite");
    volatile T value = 1;
    (void)value;
}

int main(int argc, char** argv) {
    if (argc > 1 && std::strcmp(argv[1], "invalid") == 0) {
        RTRBENCH_ROI_END(); // Mispaired boundaries must fail rather than emit misleading data.
        return 0;
    }
    if (argc > 1 && std::strcmp(argv[1], "bridge") == 0) {
        {
            RTRBENCH_LOOP("ROI bridge");
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
            RTRBENCH_ROI_BEGIN();
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
            RTRBENCH_ROI_END();
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
        return 0;
    }
    outside_roi();
    RTRBENCH_ROI_BEGIN();
    if (argc > 1 && std::strcmp(argv[1], "boundary") == 0) {
        std::this_thread::sleep_for(std::chrono::milliseconds(20)); // Function setup.
        {
            RTRBENCH_LOOP("Only the loop");
            for (int i = 0; i < 2; ++i) {
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(20)); // Cleanup.
    } else if (argc > 1 && std::strcmp(argv[1], "template") == 0) {
        template_scope<int>();
        template_scope<double>();
    } else if (argc > 1 && std::strcmp(argv[1], "overhead") == 0) {
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
    outside_roi();
}
