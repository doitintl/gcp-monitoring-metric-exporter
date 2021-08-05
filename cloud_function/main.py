from google.cloud import monitoring_v3
from google.cloud import bigquery
from datetime import timedelta
from datetime import datetime
import time
import os
import json
from google.cloud.storage import Blob
from google.cloud import storage

monitoring_client = monitoring_v3.MetricServiceClient()
export_datetime = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def get_interval(weeks_ago, days_ago, hours_ago, seconds_ago=0):
    time_now = time.time()
    start_time = get_second_delta(weeks_ago, days_ago, hours_ago, seconds_ago)
    seconds = int(time_now)
    nanos = int((time_now - seconds) * 10 ** 9)

    interval = monitoring_v3.TimeInterval(
        {
            "end_time": {"seconds": seconds, "nanos": nanos},
            "start_time": {"seconds": (seconds - int(start_time)), "nanos": nanos},
        }
    )

    return interval


def get_request_body(project_id, metric_filter, interval, page_size, full_view=True):
    project_name = f"projects/{project_id}"

    if full_view:
        view = monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
    else:
        view = monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.HEADERS

    request = {
        "name": project_name,
        "filter": metric_filter,
        "interval": interval,
        "aggregation": None,
        "view": view,
        "page_size": page_size,
    }
    return request


def get_metric_data(request):
    print("Sending request to the server...")

    results = monitoring_client.list_time_series(request)

    print("Got response from the server")

    return results


def get_second_delta(weeks, days, hours, seconds):
    return timedelta(weeks=weeks, days=days, hours=hours, seconds=seconds).total_seconds()


def parse_as_json_new_line(data):
    print("Parsing response into data points")

    points = []
    for page in data:

        metric_name = page.metric
        resource_name = page.resource

        for point in page.points:

            dict_point = {
                'time': point.interval.start_time.strftime('%d/%m/%Y %H:%M:%S'),
                'metric_type': metric_name.type,
                'resource_type': resource_name.type,
                'int_value': point.value.int64_value,
                'double_value': point.value.double_value,
                'string_value': point.value.string_value,
                'bool_value': point.value.bool_value
            }

            for key, value in metric_name.labels.items():
                dict_point[key] = value

            for key, value in resource_name.labels.items():
                dict_point[key] = value

            points.append(dict_point)

    return points


def load_to_bq(project_id, dataset, table_name, gcs_path):
    client = bigquery.Client()

    print(f"BigQuery load destination: {project_id}:{dataset}.{table_name}")

    table_id = f"{project_id}.{dataset}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON, autodetect=True,
    )

    job = client.load_table_from_uri(f'{gcs_path}', table_id, job_config=job_config)

    job.result()  # Waits for the job to complete.

    table = client.get_table(table_id)  # Make an API request.
    print(
        "Load job completed, total rows number is {} and with {} columns on {}".format(
            table.num_rows, len(table.schema), table_id
        )
    )


def write_to_local_disk(file_prefix, page_number, page_data):
    page_local_path = f'/tmp/{file_prefix}_{page_number}.jsonl'
    with open(page_local_path, 'w') as out_file:
        for data_point in page_data:
            out_file.write(json.dumps(data_point))
            out_file.write("\n")

    print("Writing operation completed with no errors")

    return page_local_path


def delete_local_file(path):
    os.remove(path)


def write_to_gcs(project_id, bucket_name, file_prefix, page_number, page_data):
    local_page_path = write_to_local_disk(file_prefix, page_number, page_data)

    storage_client = storage.Client(project=project_id)
    bucket_path = storage_client.get_bucket(bucket_name)
    blob = Blob(f'{file_prefix}/{export_datetime}/{page_number}.jsonl', bucket_path)
    blob.upload_from_filename(local_page_path)

    delete_local_file(local_page_path)


def export(request):
    request_json = request.get_json()

    print(f'Request content:{request_json}')

    env_project = request_json['project_id']

    env_bucket = request_json['bucket_name']

    env_filter = request_json['filter']

    env_weeks = int(request_json['weeks'])

    env_days = int(request_json['days'])

    env_hours = int(request_json['hours'])

    page_size = int(request_json['page_size'])

    env_bq_destination_dataset = request_json['bq_destination_dataset']

    env_bq_destination_table = request_json['bq_destination_table']

    print(f"Metric filter: {env_filter}")

    interval = get_interval(env_weeks, env_days, env_hours)

    request = get_request_body(env_project, env_filter, interval, page_size)

    raw_metrics_data = get_metric_data(request)

    page_num = 1
    parsed_page = parse_as_json_new_line(raw_metrics_data.time_series)
    write_to_gcs(env_project, env_bucket, env_bq_destination_table, page_num, parsed_page)

    while raw_metrics_data.next_page_token:
        request.update({
            'page_token': raw_metrics_data.next_page_token
        })
        raw_metrics_data = get_metric_data(request)

        page_num += 1

        parsed_page = parse_as_json_new_line(raw_metrics_data.time_series)
        write_to_gcs(env_project, env_bucket, env_bq_destination_table, page_num, parsed_page)

    gcs_path = f'gs://{env_bucket}/{env_bq_destination_table}/{export_datetime}/*'
    load_to_bq(env_project, env_bq_destination_dataset, env_bq_destination_table, gcs_path)
