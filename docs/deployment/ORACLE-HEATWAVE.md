# Oracle MySQL HeatWave deployment notes

MODO uses Oracle MySQL HeatWave for telemetry storage, analytics views, and
optional AutoML latency forecasting. Contributors do not need to install MySQL
or Docker to run the local unit tests.

## Required configuration

Copy the repository-level `.env.example` to an ignored `.env` and provide
values for an Oracle MySQL HeatWave environment you control:

- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, and `MYSQL_PASSWORD`;
- `MYSQL_DATABASE` for the application schema;
- `MYSQL_ML_SCHEMA` when its name differs from
  `ML_SCHEMA_<MYSQL_USER>`;
- `INTERNAL_API_SECRET`, shared with the Worker;
- `AUTO_RETRAIN_ENABLED=true` only after AutoML is configured.

Use a least-privilege application account where possible. Schema initialization
and model training may require a separately controlled administrative account.

## Schema initialization

`data-bridge/src/db_setup.py` creates the tables and views consumed by the API.
Run it only against a new application schema or during an approved maintenance
window:

```bash
cd data-bridge
source venv/bin/activate
python src/db_setup.py
```

Back up existing schemas first. Review the DDL before applying it to an
environment containing data.

## Optional AutoML training

`data-bridge/src/train_latency_model.py` rebuilds the training table, rotates
timestamped backups according to `TRAINING_BACKUP_KEEP`, trains a regression
model, and loads it into HeatWave memory.

Keep `AUTO_RETRAIN_ENABLED=false` until manual training succeeds and the
scheduler has been reviewed for the target environment.

## Deployment verification

These checks belong in an operator-controlled HeatWave environment; they are
not prerequisites for contributing to or reviewing the open-source code:

1. Run schema initialization against an empty or dedicated schema.
2. Confirm the API starts without missing-table or missing-view errors.
3. Verify the prune endpoint commits both retention deletes atomically.
4. Confirm HeatWave status degrades safely when optional metrics are
   unavailable.
5. Run AutoML training and confirm backup tables converge to
   `TRAINING_BACKUP_KEEP`.
6. Restart ingestion and confirm the first persisted CPU sample follows the
   warm-up sample.

Never run these checks against production without an approved backup,
maintenance window, and rollback plan.
