FUNCTION_BLOCK OutletControl
VAR_INPUT
  PositionRaw : UINT;
  FlowRaw : UINT;
  BasePermit : BOOL;
  LowLevel : BOOL;
  Armed : BOOL;
  AutoMode : BOOL;
  FlowSetting : REAL;
  ManualTarget : REAL;
  ResetFault : BOOL;
END_VAR
VAR_OUTPUT
  PositionPct : REAL;
  FlowM3s : REAL;
  TargetRaw : UINT;
  EnableCoil : BOOL;
  Permissive : BOOL;
  Moving : BOOL;
  AtTarget : BOOL;
  TravelFault : BOOL;
  MotionState : UINT;
END_VAR
VAR
  FlowLoop : PID;
  TravelTimer : TON;
  ReverseTimer : TON;
  ResetEdge : R_TRIG;
  EffectiveTarget : REAL;
  ErrorPct : REAL;
  DesiredDirection : INT;
  LastDirection : INT;
  Reversing : BOOL;
  Automatic : BOOL;
  Saturated : BOOL;
  Regulating : BOOL;
END_VAR

PositionPct := UINT_TO_REAL(PositionRaw) / 100.0;
FlowM3s := UINT_TO_REAL(FlowRaw) / 10000.0;
Permissive := BasePermit AND PositionRaw <= 10000 AND FlowRaw <= 5000;
ResetEdge(CLK := ResetFault);
IF ResetEdge.Q THEN
  TravelFault := FALSE;
END_IF;

(* Motorized outlets need a flow deadband, not continuous small reversals. *)
IF NOT AutoMode OR NOT Armed OR NOT Permissive OR LowLevel OR TravelFault THEN
  Regulating := FALSE;
ELSIF ABS(FlowSetting - FlowM3s) > 0.0075 THEN
  Regulating := TRUE;
ELSIF ABS(FlowSetting - FlowM3s) <= 0.0025 THEN
  Regulating := FALSE;
END_IF;
Automatic := AutoMode AND Armed AND Permissive AND NOT LowLevel AND NOT TravelFault AND Regulating AND NOT Saturated;
(* The native PID uses PV-SP. Negative gain and negative X0 track positive position. *)
FlowLoop(AUTO := Automatic, PV := FlowM3s * 200.0, SP := FlowSetting * 200.0,
         X0 := -PositionPct, KP := -1.0, TR := 5.0, TD := 0.0, CYCLE := T#100ms);
Saturated := Automatic AND (FlowLoop.XOUT < 0.0 OR FlowLoop.XOUT > 100.0);
IF AutoMode THEN
  EffectiveTarget := LIMIT(0.0, FlowLoop.XOUT, 100.0);
ELSE
  EffectiveTarget := LIMIT(0.0, ManualTarget, 100.0);
END_IF;
IF LowLevel THEN
  EffectiveTarget := 0.0;
END_IF;
IF AutoMode AND FlowSetting <= 0.0 THEN
  EffectiveTarget := 0.0;
END_IF;
TargetRaw := REAL_TO_UINT(EffectiveTarget * 100.0);
ErrorPct := EffectiveTarget - PositionPct;
AtTarget := ABS(ErrorPct) <= 0.5;
IF TargetRaw = 0 THEN
  AtTarget := PositionRaw = 0;
ELSIF TargetRaw >= 10000 THEN
  AtTarget := PositionRaw >= 10000;
END_IF;
DesiredDirection := 0;
IF NOT AtTarget THEN
  IF ErrorPct > 0.0 THEN
    DesiredDirection := 1;
  ELSE
    DesiredDirection := -1;
  END_IF;
END_IF;

IF Armed AND Permissive AND NOT TravelFault THEN
  IF DesiredDirection * LastDirection = -1 THEN
    Reversing := TRUE;
  END_IF;
ELSE
  Reversing := FALSE;
  LastDirection := 0;
END_IF;
ReverseTimer(IN := Reversing, PT := T#500ms);
IF ReverseTimer.Q THEN
  Reversing := FALSE;
  LastDirection := DesiredDirection;
END_IF;
EnableCoil := Armed AND Permissive AND NOT TravelFault AND NOT AtTarget AND NOT Reversing;
TravelTimer(IN := EnableCoil, PT := T#25s);
IF TravelTimer.Q THEN
  TravelFault := TRUE;
  EnableCoil := FALSE;
END_IF;
IF EnableCoil THEN
  LastDirection := DesiredDirection;
END_IF;
Moving := EnableCoil;
IF TravelFault THEN
  MotionState := 5;
ELSIF NOT Permissive THEN
  MotionState := 4;
ELSIF NOT Armed THEN
  MotionState := 0;
ELSIF Reversing THEN
  MotionState := 6;
ELSIF AtTarget THEN
  MotionState := 3;
ELSIF DesiredDirection > 0 THEN
  MotionState := 1;
ELSE
  MotionState := 2;
END_IF;
END_FUNCTION_BLOCK
