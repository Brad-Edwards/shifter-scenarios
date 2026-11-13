FUNCTION_BLOCK SiteRequests
VAR_INPUT
  IoHealthy : BOOL;
  AvailableA : BOOL;
  AvailableB : BOOL;
  LowLevel : BOOL;
  FaultA : BOOL;
  FaultB : BOOL;
  HmiStop : BOOL;
  RemoteEnableInput : BOOL;
  HmiTargetA : REAL;
  HmiTargetB : REAL;
  HmiAutoMode : BOOL;
  HmiFlow : REAL;
  HmiSequence : UINT;
  RemoteTargetA : REAL;
  RemoteTargetB : REAL;
  RemoteAutoMode : BOOL;
  RemoteFlow : REAL;
  RemoteSequence : UINT;
END_VAR
VAR_OUTPUT
  TargetA : REAL;
  TargetB : REAL;
  AutoMode : BOOL;
  FlowSetting : REAL;
  Armed : BOOL;
  RemoteEnabled : BOOL;
  Owner : UINT;
  HmiAccepted : UINT;
  RemoteAccepted : UINT;
  HmiRejected : UINT;
  RemoteRejected : UINT;
  HmiSeen : UINT;
  RemoteSeen : UINT;
  RejectReason : UINT;
  HmiRejectReason : UINT;
  RemoteRejectReason : UINT;
END_VAR
VAR RETAIN
  SavedA : REAL := 0.0;
  SavedB : REAL := 0.0;
  SavedFlow : REAL := 0.2;
END_VAR
VAR
  HmiNew : BOOL;
  RemoteNew : BOOL;
  CandidateA : REAL;
  CandidateB : REAL;
  CandidateAuto : BOOL;
  CandidateFlow : REAL;
  CandidateSource : UINT;
  Reason : UINT;
  CandidateValid : BOOL;
END_VAR

HmiNew := HmiSequence <> HmiSeen;
RemoteNew := RemoteSequence <> RemoteSeen;
RemoteEnabled := RemoteEnableInput;
CandidateSource := 0;

(* Recovery never replays a request which arrived while the site was unavailable. *)
IF NOT IoHealthy OR NOT AvailableA OR NOT AvailableB OR FaultA OR FaultB OR HmiStop THEN
  Armed := FALSE;
  RemoteEnabled := FALSE;
  Owner := 0;
END_IF;

(* A local request wins the entire two-outlet transaction. *)
IF HmiNew THEN
  CandidateSource := 1;
  CandidateA := HmiTargetA;
  CandidateB := HmiTargetB;
  CandidateAuto := HmiAutoMode;
  CandidateFlow := HmiFlow;
  IF RemoteNew THEN
    RemoteRejected := RemoteSequence;
    RemoteRejectReason := 8;
    RejectReason := 8;
  END_IF;
ELSIF RemoteNew THEN
  CandidateSource := 2;
  CandidateA := RemoteTargetA;
  CandidateB := RemoteTargetB;
  CandidateAuto := RemoteAutoMode;
  CandidateFlow := RemoteFlow;
END_IF;

IF CandidateSource <> 0 THEN
  CandidateValid := (CandidateA >= 0.0) AND (CandidateA <= 100.0)
      AND (CandidateB >= 0.0) AND (CandidateB <= 100.0)
      AND (CandidateFlow >= 0.0) AND (CandidateFlow <= 1.0);
  Reason := 0;
  IF NOT IoHealthy THEN
    Reason := 1;
  ELSIF NOT AvailableA OR NOT AvailableB THEN
    Reason := 2;
  ELSIF HmiStop THEN
    Reason := 6;
  ELSIF FaultA OR FaultB THEN
    Reason := 7;
  ELSIF (CandidateSource = 2) AND NOT RemoteEnabled THEN
    Reason := 5;
  ELSIF NOT CandidateValid THEN
    Reason := 4;
  ELSIF LowLevel AND ((CandidateAuto AND CandidateFlow > 0.0)
      OR (NOT CandidateAuto AND (CandidateA > 0.0 OR CandidateB > 0.0))) THEN
    Reason := 3;
  END_IF;
  IF Reason = 0 THEN
    SavedA := CandidateA;
    SavedB := CandidateB;
    SavedFlow := CandidateFlow;
    AutoMode := CandidateAuto;
    Armed := TRUE;
    Owner := CandidateSource;
    RejectReason := 0;
    IF CandidateSource = 1 THEN
      HmiAccepted := HmiSequence;
      HmiRejectReason := 0;
      RemoteEnabled := FALSE;
    ELSE
      RemoteAccepted := RemoteSequence;
      RemoteRejectReason := 0;
    END_IF;
  ELSE
    RejectReason := Reason;
    IF CandidateSource = 1 THEN
      HmiRejected := HmiSequence;
      HmiRejectReason := Reason;
    ELSE
      RemoteRejected := RemoteSequence;
      RemoteRejectReason := Reason;
    END_IF;
  END_IF;
END_IF;

HmiSeen := HmiSequence;
RemoteSeen := RemoteSequence;
TargetA := SavedA;
TargetB := SavedB;
FlowSetting := SavedFlow;
END_FUNCTION_BLOCK
