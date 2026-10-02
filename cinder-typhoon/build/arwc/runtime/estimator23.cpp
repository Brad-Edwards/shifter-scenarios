#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

struct Measurement {
  std::array<std::byte, 0x90> bytes{};
};
static_assert(sizeof(Measurement) == 0x90);

struct PlanningState {
  std::uint64_t vtable;
  char district_id[32];
  double reserve_ml;
  std::uint32_t quality;
  std::array<std::byte, 0x90 - 0x34> padding;
};
static_assert(sizeof(PlanningState) == 0x90);
static_assert(offsetof(PlanningState, reserve_ml) == 0x28);
static_assert(offsetof(PlanningState, quality) == 0x30);

int main(int argc, char **argv) {
  if (argc == 2 && std::string(argv[1]) == "--ordinary") {
    std::cout << "EST-CRR-23 Cairn=12.40 North=8.10 Merewick=7.65 quality=valid\n";
    return 0;
  }
  std::vector<Measurement *> measurements;
  std::unordered_map<std::string, Measurement *> by_source;
  auto *first = new Measurement;
  measurements.push_back(first);
  by_source["FIT-CRR-204B"] = first;
  auto *duplicate = new Measurement;
  delete measurements.front();
  measurements.front() = duplicate;
  // The source index intentionally retains first until calculation.
  auto *state = new PlanningState{0x4553544352523233ULL, "Cairn Reach", 12.40, 1, {}};
  auto *stale = by_source["FIT-CRR-204B"];
  std::memcpy(stale->bytes.data() + 0x28, &state->reserve_ml, sizeof(double));
  std::cout << "stale=" << static_cast<void *>(stale)
            << " replacement=" << static_cast<void *>(state) << '\n';
  delete duplicate;
  delete state;
  return stale == reinterpret_cast<Measurement *>(state) ? 0 : 3;
}
