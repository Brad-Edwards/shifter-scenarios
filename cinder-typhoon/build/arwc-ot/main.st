PROGRAM main
VAR
  LevelRaw AT %IW0 : UINT;
  PositionRaw AT %IW1 : UINT;
  FlowRaw AT %IW2 : UINT;
  Heartbeat AT %IW3 : UINT;
  TargetRaw AT %QW0 : UINT;
  LevelM : REAL;
  PositionPct : REAL;
  FlowM3s : REAL;
  HmiTargetPct : REAL;
  HmiSequence : UINT;
  HmiAccepted : UINT;
  HmiRemoteEnabled : BOOL;
  RemoteTargetPct : REAL;
  RemoteSequence : UINT;
  RemoteAccepted : UINT;
  LastRemoteSequence : UINT;
  Owner : UINT;
  IoHealthy : BOOL;
  LastHeartbeat : UINT;
  IoTimeout : TON;
  (* Full CRR site variable set — computed stubs for one-outlet compatibility *)
  UsableVolumeML : REAL;
  PositionBPct : REAL;
  FlowBM3s : REAL;
  TotalFlowM3s : REAL;
  HmiTargetBPct : REAL;
  HmiAutoMode : BOOL;
  HmiFlowM3s : REAL;
  HmiStop : BOOL;
  HmiResetFaults : BOOL;
  RemoteTargetBPct : REAL;
  RemoteAutoMode : BOOL;
  RemoteFlowM3s : REAL;
  RequestedTargetBPct : REAL;
  RequestedFlowM3s : REAL;
  AutoMode : BOOL;
  Armed : BOOL;
  HmiSeen : UINT;
  RemoteSeen : UINT;
  HmiRejected : UINT;
  RemoteRejected : UINT;
  RejectReason : UINT;
  HmiRejectReason : UINT;
  RemoteRejectReason : UINT;
  LowLevelAlarm : BOOL;
  PermissiveA : BOOL;
  PermissiveB : BOOL;
  MovingA : BOOL;
  MovingB : BOOL;
  TravelFaultA : BOOL;
  TravelFaultB : BOOL;
  AtTargetA : BOOL;
  AtTargetB : BOOL;
  MotionStateA : UINT;
  MotionStateB : UINT;
  MotorEnableA : BOOL;
  MotorEnableB : BOOL;
  ProjectRevision : UINT;
END_VAR
VAR RETAIN
  RequestedTargetPct : REAL := 0.0;
END_VAR

IoTimeout(IN := Heartbeat = LastHeartbeat, PT := T#3s);
IoHealthy := (Heartbeat > 0) AND NOT IoTimeout.Q;
LastHeartbeat := Heartbeat;
LevelM := UINT_TO_REAL(LevelRaw) / 1000.0;
PositionPct := UINT_TO_REAL(PositionRaw) / 100.0;
FlowM3s := UINT_TO_REAL(FlowRaw) / 10000.0;

(* A local request takes ownership. Remote operation needs explicit HMI consent. *)
IF IoHealthy AND HmiSequence <> HmiAccepted THEN
  IF HmiTargetPct >= 0.0 AND HmiTargetPct <= 100.0 THEN
    RequestedTargetPct := HmiTargetPct;
    HmiAccepted := HmiSequence;
    Owner := 1;
    HmiRemoteEnabled := FALSE;
  END_IF;
ELSIF IoHealthy AND HmiRemoteEnabled AND RemoteSequence <> LastRemoteSequence THEN
  IF RemoteTargetPct >= 0.0 AND RemoteTargetPct <= 100.0 THEN
    RequestedTargetPct := RemoteTargetPct;
    RemoteAccepted := RemoteSequence;
    Owner := 2;
  END_IF;
END_IF;
(* Consume inactive-channel requests; enabling remote must not replay old work. *)
LastRemoteSequence := RemoteSequence;
TargetRaw := REAL_TO_UINT(RequestedTargetPct * 100.0);

(* Compute full CRR site tags from one-outlet state *)
ProjectRevision := 364;
UsableVolumeML := 0.0;
IF LevelM > 1.0 THEN
  UsableVolumeML := (LevelM - 1.0) * 2.0;
END_IF;
LowLevelAlarm := LevelM < 0.5;
PermissiveA := IoHealthy AND NOT TravelFaultA;
PermissiveB := FALSE;
AtTargetA := ABS(PositionPct - RequestedTargetPct) < 1.0;
AtTargetB := TRUE;
MotorEnableA := PermissiveA AND (Owner > 0) AND NOT AtTargetA;
MotorEnableB := FALSE;
MovingA := MotorEnableA;
MovingB := FALSE;
MotionStateA := 0;
IF MovingA THEN MotionStateA := 1; END_IF;
MotionStateB := 0;
(* B-side outlet stubs: no second outlet in compatibility fixture *)
PositionBPct := 0.0;
FlowBM3s := 0.0;
TotalFlowM3s := FlowM3s;
RequestedTargetBPct := 0.0;
RequestedFlowM3s := 0.0;
HmiTargetBPct := 0.0;
HmiAutoMode := HmiRemoteEnabled;
HmiFlowM3s := 0.0;
RemoteTargetBPct := 0.0;
RemoteAutoMode := FALSE;
RemoteFlowM3s := 0.0;
AutoMode := HmiAutoMode;
Armed := HmiRemoteEnabled;
HmiSeen := HmiSequence;
RemoteSeen := RemoteSequence;
HmiRejected := 0;
RemoteRejected := 0;
RejectReason := 0;
HmiRejectReason := 0;
RemoteRejectReason := 0;
END_PROGRAM
