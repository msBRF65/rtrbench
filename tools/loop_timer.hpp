#ifndef RTRBENCH_LOOP_TIMER_HPP
#define RTRBENCH_LOOP_TIMER_HPP

// Main-thread loop clocks within zsim ROIs: inclusive elapsed and exclusive partition.
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
    long long nanoseconds = 0, inclusive = 0;
    unsigned long long entries = 0, calls = 0;
};
class Ledger {
    std::vector<Region> regions;
    struct Frame { size_t id; long long started; bool observed_roi; };
    std::vector<Frame> stack;
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
            else regions[stack.back().id].nanoseconds += ns;
        }
        last = now;
    }
public:
    Ledger() { regions.reserve(64); stack.reserve(16); }
    size_t add(const char* name, const char* file, int line) {
        if (owner != std::this_thread::get_id()) std::abort();
        // One source callsite can be instantiated by multiple template types.
        for (size_t i = 0; i < regions.size(); ++i)
            if (regions[i].name == name && regions[i].file == file && regions[i].line == line) return i;
        regions.push_back({name, file, line});
        return regions.size()-1;
    }
    void begin() {
        account();
        if (active) std::abort();
        active = true;
        for (auto& frame : stack) frame.observed_roi = true;
    }
    void end() { account(); if (!active) std::abort(); active = false; }
    void enter(size_t id) {
        account();
        stack.push_back({id, total, active});
        ++regions[id].entries;
    }
    void leave(size_t id) {
        account();
        if (stack.empty() || stack.back().id != id) std::abort();
        const auto frame = stack.back();
        // The logical ROI clock advances only while active. Nested regions remain
        // inside this interval, but paused rollouts and pre/post-ROI work do not.
        if (frame.observed_roi) {
            regions[id].inclusive += total - frame.started;
            ++regions[id].calls;
        }
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
        out << "region,file,line,calls,exclusive_ns,inclusive_ns,total_roi_ns\n";
        std::ofstream coverage(std::string(path) + ".coverage.csv");
        if (!coverage) std::abort();
        coverage << "region,file,line,entries,roi_calls,status\n";
        for (const auto& r : regions) {
            coverage << r.name << ',' << r.file << ',' << r.line << ',' << r.entries << ','
                     << r.calls << ',' << (r.calls ? "measured" : "outside_roi") << '\n';
            // Off-ROI-only entries are metadata, never fabricated zero loop timings.
            if (!r.calls) continue;
            out << r.name << ',' << r.file << ',' << r.line << ',' << r.calls << ','
                << r.nanoseconds << ',' << r.inclusive << ',' << total << '\n';
        }
        out << "Unattributed ROI,,0,0," << rest << ",," << total << '\n';
        coverage.flush();
        if (!coverage) std::abort();
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
