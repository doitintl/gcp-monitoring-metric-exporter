# Parameters to configure #
PROJECT_ID="<PROJECT-ID>"

# Cloud Function Parameters #
CF_REGION="<CLOUD-FUNCTION-REGION>"
TIMEOUT=540 # INT - In seconds max=540
MEMORY=128 # INT - In MB max=8192MB
PAGE_SIZE=500 # INT

# Cloud Scheduler Parameters #
EXPORT_NAME="<EXPORT-JOB-NAME>" # Keep this name unique for each metric export, this is the scheduler name as well as the table name in BigQuery
TIME_ZONE="<SCHEDULER-TIME-ZONE>"
SCHEDULE="<CRON-EXPRESSION>" # The export job will be triggered by this expression, for more information please look at https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules.
WEEKS=0 # INT
DAYS=0 # INT
HOURS=1 # INT
FILTER='metric.type = "storage.googleapis.com/storage/object_count"' # Change to your metric filter

# BigQuery Parameters - Configure only at First deployment #
BQ_DATASET="metric_exporter_staging_dataset" #
BQ_LOCATION="US"


# -------------------------------------------------------------------------------------------------------------------- #

# System parameters - Don't change #

# Cloud Function Parameters #

CF_NAME="metric_exporter"
CF_SA="metric-exporter-cf-sa@"$(PROJECT_ID)".iam.gserviceaccount.com"
RUNTIME="python37"
SOURCE_PATH="./cloud_function" # Source file path for the cloud function
ENTRY_POINT="export"

# Cloud Scheduler Parameters #

SCHEDULER_SA="metric-exporter-scheduler-sa@"$(PROJECT_ID)".iam.gserviceaccount.com" # Cloud Function Invoker
HEADERS="Content-Type=application/json,User-Agent=Google-Cloud-Scheduler"

# BigQuery Parameters #
BQ_TABLE=$(EXPORT_NAME)

# GCS Bucket Parameters#
BUCKET_NAME="$(PROJECT_ID)-Metric-Exporter"

# System Parameters - Don't change #

MSG_TMP_DIR="./msg_tmp"
MSG_BODY_FILE_NAME="msg.json"

# -------------------------------------------------------------------------------------------------------------------- #

deploy_cloud_function:
	gcloud functions deploy $(CF_NAME) --region=$(CF_REGION) --runtime=$(RUNTIME) --trigger-http --source=$(SOURCE_PATH) \
	--entry-point=$(ENTRY_POINT) --project=$(PROJECT_ID) --service-account=$(CF_SA) \
	--memory=$(MEMORY) --timeout=$(TIMEOUT)

deploy_scheduler: test_filter_api build_json_msg
	gcloud scheduler jobs create http $(EXPORT_NAME) --project=$(PROJECT_ID) --schedule=$(SCHEDULE) \
	--uri=$https://$(CF_REGION)-$(PROJECT_ID).cloudfunctions.net/$(CF_NAME) --http-method=POST \
	--headers=$(HEADERS) \
	--oidc-service-account-email=$(SCHEDULER_SA) \
	--message-body-from-file=$(MSG_TMP_DIR)"/"$(MSG_BODY_FILE_NAME) \
	--time-zone=$(TIME_ZONE)

test_filter_api:
	python validate_filter.py --project=$(PROJECT_ID) --filter=$(FILTER)

build_json_msg:
	python build_message_body.py --project=$(PROJECT_ID) --filter=$(FILTER) --weeks=$(WEEKS) --days=$(DAYS) --hours=$(HOURS) --bq_destination_dataset=$(BQ_DATASET) \
	--bq_destination_table=$(BQ_TABLE) --MSG_TMP_DIR=$(MSG_TMP_DIR) --MSG_BODY_FILE_NAME=$(MSG_BODY_FILE_NAME) --BUCKET_NAME=$(BUCKET_NAME) --PAGE_SIZE=$(PAGE_SIZE)

clean:
	rm $(MSG_TMP_DIR)"/"$(MSG_BODY_FILE_NAME)

delete_cloud_function:
	gcloud functions delete $(CF_NAME) --region=$(CF_REGION) --project=$(PROJECT_ID)

delete_scheduler:
	gcloud scheduler jobs delete $(EXPORT_NAME) --project=$(PROJECT_ID)

create_bq_dataset:
	bq --location=$(BQ_LOCATION) mk --dataset $(PROJECT_ID):$(BQ_DATASET)

get_cf_sa_name:
	@echo $(CF_SA)

get_scheduler_sa_name:
	@echo $(SCHEDULER_SA)

schedule_metric_export: deploy_scheduler clean

full_deploy: deploy_cloud_function schedule_metric_export

print_dummy:
	echo $(my_name)