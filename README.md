# Weather Histogram Creator

An application that takes the log file input (below) and creates a tsv file containing histogram bins of forecasted high temperatures of the locations discovered in the input log.

## Input File Download
http://s3.amazonaws.com/thetradedesk-ops/histogram_input

## Requirements
1. Weather API, DarkSky API, and Visual Crossing API keys
2. Python and/or Docker installed

## Usage
#### Run locally:
```python
python CreateWeatherHistogram.py
```
#### Run with specific arguments:
```python
python CreateWeatherHistogram.py --input ./histogram_input --output ./histogram.tsv --bucket-count 5
```
#### Run within a Docker container:
```
# Build the image.
docker build -t {IMAGE NAME} .

# Run with no arguments.
docker run --mount "type=bind,source=$(pwd),target=/app" {IMAGE NAME}

# Run with specific arguments.
docker run --mount "type=bind,source=$(pwd),target=/app" {IMAGE NAME} --input ./{YOUR INPUT FILE} --output {YOUR OUTPUT FILE} --bucket-count {ANY NUMBER OF BUCKETS}
```

## Notes:
- The very first time you call this program (without previously cached location/temperature data) will take roughly 30mins-1hour to completely run.
- This app uses 2 APIs to retrieve forecast information. If limits are reached before all data is found, the histogram will be created from only the found information (successful API calls and previously cached data).
- Visual Crossing API requires the VC_limit_date.txt file because there's no current way to retrieve total amount of calls made so far. This file prevents us from calling the API after the limit has been reached if we decide to run the program multiple times.

## Future Improvements:
- Utilize more APIs in order to cover a bigger amount of data.
- Have more extensive statements that catch edge cases.
- Find a better way to cache API calls (such as with Requests-cache.)
