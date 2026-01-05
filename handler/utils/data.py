import numpy as np
import pandas as pd

from utils.logger import LOGGER


class CleaningError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


def convert_df(header: list[str], rows: list[list]) -> pd.DataFrame:
    """
    Correct any length mismatches between data and header row, then combine into single dataframe
    """
    df: pd.DataFrame = pd.DataFrame(rows)
    col_diff: int = len(df.columns) - len(header)

    if col_diff > 0:
        header.extend([f"UNK_{idx}" for idx in range(0, col_diff)])
    elif col_diff < 0:
        for idx in range(0, -1 * col_diff):
            df[f"UNK_{idx}"] = ""
    df.columns = header
    return df


# TODO: load agency/county (auxilliary data) from S3
def load_agency_county() -> dict:
    # agency_county = datasets.dataframes['agencies_and_counties']
    # agency_county = agency_county.set_index('agency')['county'].to_dict()
    return {}


def upcase_strip_string_cells(df):
    for c in df.columns:
        df[c] = df[c].apply(
            lambda x: x if not isinstance(x, str) else x.strip().upper()
        )
    return df


def standardize_race(race):
    WHITE, BLACK, HISPANIC, OTHER = "WHITE,BLACK,HISPANIC,OTHER".split(",")
    # RACES = [WHITE, BLACK, HISPANIC, OTHER] # FIXME: why is this unused?
    if pd.isnull(race) or not race:
        return None
    race = race.lower()
    if "anglo" in race or "white" in race or "caucasian" in race or race == "ao":
        return WHITE
    elif "black" in race or "african" in race:
        return BLACK
    elif (
        ("hispanic" in race or "latino" in race)
        and ("non hispanic" not in race)
        and ("not hispanic" not in race)
    ):
        return HISPANIC
    else:
        return OTHER


def standardize_race_cols(df) -> pd.DataFrame:
    cols = [
        c for c in df.columns if "race" in c.split("_") or "ethnicity" in c.split("_")
    ]
    for col in cols:
        df[col] = df[col].apply(standardize_race)
    return df


def standardize_gender(gender) -> str:
    MALE = "MALE"
    FEMALE = "FEMALE"
    GENDERS_UNKNOWN = ["u"]
    # GENDERS = [MALE, FEMALE] # why is this unused?
    if pd.isnull(gender):
        return None
    gender = gender.strip().lower()
    if not gender:
        return None
    if gender in ("m", "male", "man"):
        return MALE
    elif gender in ("f", "female", "woman"):
        return FEMALE
    elif gender in GENDERS_UNKNOWN:
        return None
    else:
        raise CleaningError('Unrecognized gender: "%s"' % gender)


def standardize_gender_cols(df) -> pd.DataFrame:
    cols = [c for c in df.columns if "gender" in c.split("_") or "sex" in c.split("_")]
    for col in cols:
        df[col] = df[col].apply(standardize_gender)
    return df


def numericalize_age_cols(df) -> pd.DataFrame:
    cols = [c for c in df.columns if "age" in c.split("_")]
    for c in cols:
        print("Numericalizing column %s" % c)
        bad_values = []
        new_values = []
        for value in df[c]:
            if pd.isnull(value):
                new_values.append(value)
            else:
                try:
                    newval = float(value)
                except ValueError:
                    newval = np.nan
                    bad_values.append(value)
                new_values.append(newval)
        df[c] = new_values
        df[c] = df[c].astype(float)
        if bad_values:
            print("Replaced %d bad values with NA:" % len(bad_values))
            print("Unique bad values:", set(bad_values))
    return df


def convert_date_cols(df) -> pd.DataFrame:  # TODO: add logger, fix types
    cols = [c for c in df.columns if "date" in c.split("_")]
    cols = [c for c in cols if "_n_a" not in c and "na" not in c.split("_")]
    for c in cols:
        print("Converting column %s to datetime" % c)
        bad_values = []
        new_values = []
        for value in df[c]:
            if pd.isnull(value):
                new_values.append(value)
            else:
                try:
                    newval = pd.to_datetime(value)
                except ValueError:
                    newval = np.nan
                    bad_values.append(value)
                new_values.append(newval)
        df[c] = new_values
        df[c] = pd.to_datetime(df[c])
        if bad_values:
            print("Replaced %d bad values with NaT:" % len(bad_values))
            print("Unique bad values:", set(bad_values))
    return df


def standardize_name(name):
    if pd.isnull(name):
        return None
    name = str(name)
    parts = name.split()
    parts = ["".join(ch for ch in p if ch.isalnum() or ch == "-") for p in parts]
    name = " ".join([p for p in parts if p])
    return name if name else None


def insert_col_after(df, to_insert, name, after):
    cols = list(df.columns)
    i = cols.index(after)
    newcols = cols[: (i + 1)] + [name] + cols[(i + 1) :]
    df[name] = to_insert
    return df[newcols]


def reorder_columns_and_check(df, new_order):
    """Return dataframe with reordered columns, making sure we didn't leave any columns out."""
    if len(new_order) != len(set(new_order)):
        raise CleaningError("Duplicate columns in new_order! Plz fix.")
    if len(df.columns) != len(set(df.columns)):
        raise CleaningError("Duplicate columns in original dataframe! Plz fix.")

    # Make sure we are only reordering columns, not dropping any
    if set(new_order) != set(df.columns):
        # At least one column exists in the old but not the new order, or vice versa.
        old_cols = list(df.columns)
        messages = []
        for c in old_cols:
            if c not in new_order:
                messages.append(
                    "Column '%s' from the original dataframe is missing in new_order"
                    % c
                )
        for c in new_order:
            if c not in old_cols:
                messages.append(
                    "Column '%s' in new_order does not exist in the original dataframe"
                    % c
                )
        raise CleaningError("\n".join(messages))

    return df[new_order]


def float_or_nan(val):
    try:
        return float(val)
    except ValueError:
        pass
    except TypeError:
        pass
    print("- BAD VALUE (returning NaN):", val)
    return np.nan


def clean_floats(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for c in cols:
        LOGGER.debug("Converting", c)
        df[c] = df[c].apply(float_or_nan).astype(float)
    return df


def fix_coroner(result):
    if pd.isnull(result):
        return None
    result = result.strip()
    if result.startswith("YES"):
        return "YES"
    elif result.startswith("NO"):
        return "NO"
    return None


def fix_other_behavior(data: pd.DataFrame) -> pd.DataFrame:
    behavior = []
    for other, specify in zip(data["other_behavior"], data["specify_other_behavior"]):
        if pd.notnull(specify):
            behavior.append(specify)
        else:
            try:
                other = float(other)
                if other == 0.0:
                    behavior.append(None)
                    continue
            except TypeError:
                pass
            except ValueError:
                pass
            behavior.append(other)

    data["other_behavior"] = pd.Series(behavior, index=data.index)
    data.drop("specify_other_behavior", axis=1, inplace=True)
    return data


def merge_dupes(frame):
    """Master merge function. Creates one record from several that are known duplicates."""
    # Ignore BJS records (these are from and old data dump),
    # unless there is no other option.
    form_versions_seen = set(frame["form_version"])
    if "V_BJS" in form_versions_seen and len(form_versions_seen) > 1:
        frame = frame[frame["form_version"] != "V_BJS"]
        if len(frame) == 1:
            return frame.iloc[0], "Keeping the only non-BJS record"

    # If one record has a higher version_number than the rest, keep that one.
    # If one record has a more recent report_date than the rest, keep that one.
    max_cols = ["version_number", "report_date"]
    for c in max_cols:
        maxval = frame[
            c
        ].max()  # Implicitly ignores missing values, unless only missing values exist
        if pd.notnull(maxval):
            frame = frame[frame[c] == maxval]
            if len(frame) == 1:
                return frame.iloc[0], "Keeping the record with greatest %s" % c

    # Otherwise, there's no way to flag the "one" right record (that I know of).
    # So we gotta merge them somehow...
    merged_rec = pd.Series(
        index=frame.columns, name=1000000 + frame.index[0]
    )  # Give it a new, unique index
    awk = False
    for c in frame.columns:
        notnull = frame[c][frame[c].notnull()]

        # If all records have NA for this column, leave it as NA
        if len(notnull) == 0:
            merged_rec[c] = frame[c].iloc[0]
            continue

        # Only 1 unique not-null value? Keep that one.
        if len(notnull) == 1 or len(set(notnull)) == 1:
            merged_rec[c] = notnull.iloc[0]
            continue

        # Are we trying to merge record IDs? That's impossible anyway,
        # let's just concatenate them.
        if c == "cdr_cdr_name":
            merged_rec[c] = "-".join(notnull)
            continue

        # Well, poop. Multiple unique values for this column.
        # Take the most popular one ¯\_(ツ)_/¯
        # (Which will just be a random one if there's a tie ¯\_(ツ)_/¯ )
        awk = True
        vc = notnull.value_counts()
        keeper = vc.index[0]
        if vc.iloc[0] > vc.iloc[1]:
            print(
                "  > Problem with column %s, keeping the most popular value, '%s'"
                % (c, keeper),
                notnull.values,
            )
        else:
            print(
                "  > Problem with column %s, keeping an arbitrary tied-for-most-popular value, '%s'"
                % (c, keeper),
                notnull.values,
            )
        merged_rec[c] = keeper

    merged_rec["cdr_cdr_name"] = "MERGED-DUPLICATES-%s" % merged_rec["cdr_cdr_name"]
    if awk:
        return merged_rec, "Merged awkwardly"
    else:
        return merged_rec, "Merged smoothly enough"


def dedup_cdr_by_col(cdr, cols):
    """Given a cdr dataframe, and a set of columns to use to identify duplicates, dedups/merges as needed."""
    dups = cdr[cdr.duplicated(subset=cols, keep=False)]
    if not len(dups):
        return cdr
    unmerged_frames = []
    merged_records = []
    merge_methods = []
    for _, frame in dups.groupby(cols):
        rec, meth = merge_dupes(frame)
        unmerged_frames.append(frame)
        merged_records.append(rec)
        merge_methods.append(meth)
        if "awkward" in meth:
            print("...awkward merge complete for records at indices", frame.index)

    return (
        pd.concat([cdr.drop(dups.index), pd.DataFrame.from_records(merged_records)]),
        unmerged_frames,
        merged_records,
        merge_methods,
    )
