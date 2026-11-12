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
END_PROGRAM
