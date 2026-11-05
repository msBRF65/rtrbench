#ifndef RTRBENCH_LOOP_TIMER_HPP
#define RTRBENCH_LOOP_TIMER_HPP

// Opt-in, main-thread, exclusive wall-clock accounting within zsim ROIs.
#if defined(RTRBENCH_MEASURE_LOOPS) || defined(RTRBENCH_MEASURE_ROI)
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

namespace rtrbench {
using Clock = std::chrono::steady_clock;
struct Region {
    std::string name, file;
    int line;
    long long nanoseconds = 0;
    unsigned long long calls = 0;
};
class Ledger {
    std::vector<Region> regions;
    std::vector<size_t> stack;
    Clock::time_point last;
    std::thread::id owner = std::this_thread::get_id();
    bool active = false;
    long long total = 0, rest = 0;
    void account() {
        if (owner != std::this_thread::get_id()) std::abort();
        const auto now = Clock::now();
        if (active) {
            const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(now-last).count();
            total += ns;
            if (stack.empty()) rest += ns;
            else regions[stack.back()].nanoseconds += ns;
        }
        last = now;
    }
public:
    size_t add(const char* name, const char* file, int line) {
        if (owner != std::this_thread::get_id()) std::abort();
        regions.push_back({name, file, line});
        return regions.size()-1;
    }
    void begin() { account(); if (active) std::abort(); active = true; }
    void end() { account(); if (!active) std::abort(); active = false; }
    void enter(size_t id) { account(); stack.push_back(id); ++regions[id].calls; }
    void leave(size_t id) {
        account();
        if (stack.empty() || stack.back() != id) std::abort();
        stack.pop_back();
    }
    ~Ledger() {
        const char* path = std::getenv("RTRBENCH_TIMING_FILE");
        if (!path) return;
        if (active || !stack.empty()) std::abort();
        long long sum = rest;
        for (const auto& region : regions) sum += region.nanoseconds;
        if (sum != total) std::abort();
        std::ofstream out(path);
        if (!out) std::abort();
        out << "region,file,line,calls,exclusive_ns,total_roi_ns\n";
        for (const auto& r : regions)
            out << r.name << ',' << r.file << ',' << r.line << ',' << r.calls << ','
                << r.nanoseconds << ',' << total << '\n';
        out << "Unattributed ROI,,0,0," << rest << ',' << total << '\n';
        out.flush();
        if (!out) std::abort();
    }
};
inline Ledger& ledger() { static Ledger value; return value; }
struct Scope {
    size_t id;
    explicit Scope(size_t value): id(value) { ledger().enter(id); }
    ~Scope() { ledger().leave(id); }
    Scope(const Scope&) = delete;
    Scope& operator=(const Scope&) = delete;
};
}
#define RTR_JOIN_(a,b) a##b
#define RTR_JOIN(a,b) RTR_JOIN_(a,b)
#ifdef RTRBENCH_MEASURE_LOOPS
#define RTRBENCH_LOOP(name) \
    static const size_t RTR_JOIN(rtr_id_,__LINE__) = rtrbench::ledger().add(name,__FILE__,__LINE__); \
    rtrbench::Scope RTR_JOIN(rtr_scope_,__LINE__)(RTR_JOIN(rtr_id_,__LINE__))
#else
#define RTRBENCH_LOOP(name) do {} while (false)
#endif
#define RTRBENCH_ROI_BEGIN() rtrbench::ledger().begin()
#define RTRBENCH_ROI_END() rtrbench::ledger().end()
#else
#define RTRBENCH_LOOP(name) do {} while (false)
#define RTRBENCH_ROI_BEGIN() do {} while (false)
#define RTRBENCH_ROI_END() do {} while (false)
#endif
#endif
