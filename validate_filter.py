import sys
import time
import argparse
from datetime import timedelta
from google.cloud import monitoring_v3


monitoring_client = monitoring_v3.MetricServiceClient()


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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument("--project", required=True)

    parser.add_argument("--filter", required=True)

    args = parser.parse_args()

    project = args.project

    filter_exp = args.filter

    interval_obj = get_interval(weeks_ago=0, days_ago=0, hours_ago=0, seconds_ago=1)

    request_body = get_request_body(project_id=project, metric_filter=filter_exp,
                                    interval=interval_obj, page_size=1, full_view=False)

    try:
        response = get_metric_data(request_body)
    except Exception as e:
        print("An error has occurred during API test call.\nPlease look at the following details:", e)
        sys.exit(1)

    print("API call tested successfully")
    sys.exit(0)


