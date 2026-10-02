#include <array>
#include <iomanip>
#include <iostream>
#include <map>
#include <string>
#include <vector>

struct World {
    std::map<std::string, double> setpoint;
    std::map<std::string, double> position;
    std::map<std::string, double> flow;
    std::map<std::string, double> reserve;
    std::map<std::string, std::string> mode;
    std::map<std::string, int> revision;
    double cached_reserve = 13.40;
    bool approved = false;
};

static World initial_world() {
    World world;
    world.setpoint = {{"OutletGroup", 0.0}, {"GateA", 0.0}, {"GateB", 0.0}};
    world.position = {{"GateA", 0.0}, {"GateB", 0.0}};
    world.flow = {{"OutletGroup", 0.0}, {"GateA", 0.0}, {"GateB", 0.0}};
    world.reserve = {{"Reservoir", 13.40}, {"Buffer", 180.0}};
    world.mode = {{"OutletGroup", "DRY_PERIOD_MANAGED"}};
    world.revision = {{"Reservoir", 19}, {"OutletGroup", 19}, {"GateA", 19}, {"GateB", 19}, {"Buffer", 19}};
    return world;
}

static void command_apply(World &world, double target) {
    world.setpoint["OutletGroup"] = target * 2.0;
    world.setpoint["GateA"] = target;
    world.setpoint["GateB"] = target;
}

static void ramp_limit(World &world, double step) {
    for (const auto &gate : {"GateA", "GateB"}) {
        double difference = world.setpoint[gate] - world.position[gate];
        if (difference > step) difference = step;
        if (difference < -step) difference = -step;
        world.position[gate] += difference;
    }
}

static double flow_integrate(World &world, double seconds) {
    world.flow["GateA"] = world.position["GateA"];
    world.flow["GateB"] = world.position["GateB"];
    world.flow["OutletGroup"] = world.flow["GateA"] + world.flow["GateB"];
    return world.flow["OutletGroup"] * seconds / 1000.0;
}

static void reserve_update(World &world, double volume_ml) {
    world.reserve["Reservoir"] -= volume_ml;
}

static void approval_check(World &world, double requested_ml, double committed_ml) {
    world.approved = world.cached_reserve - requested_ml >= committed_ml;
}

static void structure() {
    std::cout << "{\"record_id\":\"REPLAY-CRR-R19\",\"revision\":19,"
                 "\"runtime\":\"C++20 ECS\",\"entities\":["
                 "{\"entity\":\"Reservoir\",\"components\":[\"Reserve\",\"Revision\"]},"
                 "{\"entity\":\"OutletGroup\",\"components\":[\"Setpoint\",\"Flow\",\"Mode\",\"Revision\"]},"
                 "{\"entity\":\"GateA\",\"components\":[\"Setpoint\",\"Position\",\"Flow\",\"Revision\"]},"
                 "{\"entity\":\"GateB\",\"components\":[\"Setpoint\",\"Position\",\"Flow\",\"Revision\"]},"
                 "{\"entity\":\"Buffer\",\"components\":[\"Reserve\",\"Revision\"]}],"
                 "\"outlet_example\":{\"outlet_group\":\"OG-CRR-02\","
                 "\"entity\":\"OutletGroup\",\"gates\":[\"GateA\",\"GateB\"]}}\n";
}

static void inputs() {
    std::cout << "[{\"case_id\":\"ECS-CREATE-R19\",\"operation\":\"create-world\"},"
                 "{\"case_id\":\"ECS-COMMAND-R19\",\"target_each_gate_m3s\":0.50,\"elapsed_seconds\":0},"
                 "{\"case_id\":\"ECS-RAMP-R19\",\"target_each_gate_m3s\":0.50,\"elapsed_seconds\":20},"
                 "{\"case_id\":\"ECS-DISPUTED-R19\",\"requested_volume_ml\":1.00,"
                 "\"committed_allocation_ml\":12.00}]\n";
}

static void transitions() {
    World world = initial_world();
    command_apply(world, 0.50);
    World command = world;
    ramp_limit(world, 0.10);
    double volume = flow_integrate(world, 20.0);
    reserve_update(world, volume);
    approval_check(world, volume, 12.00);
    std::cout << std::fixed << std::setprecision(3)
              << "[{\"case_id\":\"ECS-CREATE-R19\",\"created_entities\":5,\"created_components\":16},"
              << "{\"case_id\":\"ECS-COMMAND-R19\",\"system\":\"CommandApply\","
                 "\"gate_setpoint_m3s\":0.500,\"gate_position_m3s\":" << command.position["GateA"] << "},"
              << "{\"case_id\":\"ECS-RAMP-R19\",\"systems\":[\"CommandApply\",\"RampLimit\","
                 "\"FlowIntegrate\",\"ReserveUpdate\",\"ApprovalCheck\"],"
                 "\"gate_position_m3s\":" << world.position["GateA"]
              << ",\"aggregate_flow_m3s\":" << world.flow["OutletGroup"]
              << ",\"integrated_volume_ml\":" << volume
              << ",\"reserve_ml\":" << world.reserve["Reservoir"] << "},"
              << "{\"case_id\":\"ECS-DISPUTED-R19\",\"cached_reserve_ml\":13.400,"
                 "\"requested_volume_ml\":1.000,\"post_update_reserve_ml\":12.400,"
                 "\"committed_allocation_ml\":12.000,\"old_approved\":true}]\n";
}

static void condition() {
    World world = initial_world();
    approval_check(world, 1.00, 12.00);
    std::cout << "{\"record_id\":\"APPROVAL-COND-R19\",\"revision\":19,"
                 "\"system_order\":[\"CommandApply\",\"RampLimit\",\"FlowIntegrate\","
                 "\"ReserveUpdate\",\"ApprovalCheck\"],"
                 "\"read_binding\":\"pre-ReserveUpdate cached Reserve\","
                 "\"predicate\":\"cached_reserve_ml-requested_volume_ml>=committed_allocation_ml\","
                 "\"cached_reserve_ml\":13.40,\"requested_volume_ml\":1.00,"
                 "\"committed_allocation_ml\":12.00,\"projected_reserve_ml\":12.40,"
                 "\"approved\":" << (world.approved ? "true" : "false") << "}\n";
}

static void witness() {
    std::cout << "{\"record_id\":\"TRACE-R19-DISPUTED\",\"revision\":19,"
                 "\"request_volume_ml\":1.00,\"committed_allocation_ml\":12.00,"
                 "\"retained_replay\":{\"project\":\"CRR-CTRL-R19\","
                 "\"cached_reserve_ml\":13.40,\"post_update_reserve_ml\":12.40,"
                 "\"decision\":\"accepted\"},"
                 "\"current_model\":{\"project\":\"CRR-CTRL-R21\","
                 "\"independent_pre_update_reserve_ml\":12.40,"
                 "\"post_update_reserve_ml\":11.40,\"decision\":\"rejected\"},"
                 "\"live_authority\":false,\"replaces_current_observation\":false}\n";
}

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    std::string mode(argv[1]);
    if (mode == "structure") structure();
    else if (mode == "inputs") inputs();
    else if (mode == "transitions") transitions();
    else if (mode == "condition") condition();
    else if (mode == "witness") witness();
    else return 64;
    return 0;
}
