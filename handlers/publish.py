from publisher.compress import compress_data
from publisher.config import CONFIGS, OUTPUT_S3_BUCKET_NAME

from shared.logger import LOGGER
from shared.s3 import get_s3_json, save_s3_json


def main():
    config: dict = CONFIGS.get(
        "cdr", {}
    )  # TODO: when OIS ported, loop over both OIS and CDR
    slider_data, compressed, compressed_new = compress_data(config)

    # generate files: compressed, compressed new, zipped compressed new
    LOGGER.debug("... Saving data to S3 ...")
    save_s3_json(
        compressed,
        OUTPUT_S3_BUCKET_NAME,
        f"{config.get('OUTFILE_PREFIX')}_compressed.json",
    )
    save_s3_json(
        compressed_new,
        OUTPUT_S3_BUCKET_NAME,
        f"{config.get('OUTFILE_PREFIX')}_compressed_new.json",
    )
    save_s3_json(
        compressed_new,
        OUTPUT_S3_BUCKET_NAME,
        f"{config.get('OUTFILE_PREFIX')}_compressed_new.json",
        True,
    )

    # TEMP FIX: append CDR to existing slider data until generating OIS slider too; website data viz gets all slider data from one file
    # TODO: see if website can stop getting all slider data from single file
    # TODO: turn off OIS processing
    LOGGER.debug("... Updating slider data ...")
    all_slider_data = get_s3_json(OUTPUT_S3_BUCKET_NAME, "all_slider_data.json")
    all_slider_data["cdr"] = slider_data
    save_s3_json(all_slider_data, OUTPUT_S3_BUCKET_NAME, "all_slider_data.json")


if __name__ == "__main__":
    main()
