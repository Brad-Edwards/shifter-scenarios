# Cairn Reach history provenance

Reference: `CRR-HIST-PROV-R364`

The controller publishes each value as an OPC UA `DataValue`. Its source time
belongs to the data source. The collector records when it received the value,
and PostgreSQL records when it inserted the row. These are three different
clocks:

- `source_time`: time attached to the controller value;
- `collected_time`: time Telegraf collected that value;
- `ingested_at`: PostgreSQL insertion time.

Use `process_quality` before using a measurement. `transport_quality` describes
the OPC UA transfer, while process quality also accounts for current field-I/O
health and sample age. A Good transport value can therefore still be unusable
as a process observation.

The native historian uses the series and unit from `historian_tag_catalog`.
For a collection interruption, compare consecutive `source_time` values for one
series, then inspect the collection and insertion times on both sides. A gap in
source time does not by itself prove that an engineering unit changed.

The register uses zero-based Modbus PDU offsets. Function 4 reads input
registers. The familiar 30001-style reference is display notation, not the PDU
offset and not the OpenPLC IEC address.

Example starting query (choose the relevant series and time range):

```sql
SELECT source_time, collected_time, ingested_at, tag, value, unit,
       transport_quality, process_quality,
       source_time - lag(source_time) OVER (PARTITION BY tag ORDER BY source_time)
         AS source_gap
FROM process_history
WHERE tag = 'flow_b_m3s'
ORDER BY source_time;
```
