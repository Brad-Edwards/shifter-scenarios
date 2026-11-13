FUNCTION_BLOCK SiteInputs
VAR_INPUT
  LevelRaw : UINT;
  Heartbeat : UINT;
END_VAR
VAR_OUTPUT
  LevelM : REAL;
  UsableVolumeML : REAL;
  IoHealthy : BOOL;
  LowLevelAlarm : BOOL;
END_VAR
VAR
  LastHeartbeat : UINT;
  Freshness : TON;
END_VAR

Freshness(IN := Heartbeat = LastHeartbeat, PT := T#3s);
IoHealthy := (Heartbeat > 0) AND NOT Freshness.Q AND (LevelRaw <= 10000);
LastHeartbeat := Heartbeat;
LevelM := UINT_TO_REAL(LevelRaw) / 1000.0;
UsableVolumeML := MAX(0.0, (LevelM - 1.0) * 2.0);
IF LevelM <= 1.0 THEN
  LowLevelAlarm := TRUE;
ELSIF LevelM >= 1.2 THEN
  LowLevelAlarm := FALSE;
END_IF;
END_FUNCTION_BLOCK
