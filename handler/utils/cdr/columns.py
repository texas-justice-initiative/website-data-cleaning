def rename_columns(columns: list[str]) -> dict:
    col_renames = {}
    for col in columns:
        new_name = "".join([char if char.isalnum() else " " for char in col.lower()])
        new_name = "_".join(new_name.strip().split())
        col_renames[col] = new_name
    return col_renames


def sort_columns() -> list[str]:
    """
    Both forms
    - Age At Time Of Death
    - Agency Address
    - Agency City
    - Agency Name
    - Agency Zip
    - CDR: CDR Name
    - City
    - County
    - Date of Birth
    - Date/Time of Custody or Incident
    - Death Date and Time
    - Death Location
    - Death Location Elsewhere
    - Entry Date Time
    - Entry Date Time N/A
    - First Name
    - Middle Name
    - Last Name
    - Suffix
    - Manner of Death
    - Manner of Death Description
    - Means of Death
    - Means of Death Other
    - Medical Cause of Death
    - Medical Examinor/Coroner Evalution?
    - Medical Treatment
    - Offense 1
    - Offense 2
    - Offense 3
    - Pre existing medical condition?
    - Report Date
    - Sex
    - Specific Type of Custody/Facility
    - Street Address
    - Type of Custody
    - Type of Offense
    - Type of Offense, Other
    - Version Number
    - Version Type
    - Were the Charges:
    - Who caused the death?
    - form_version
    - Type of Restraint
    - Under Restraint

    2005 form only

    - Agency County
    - Custody Date NA
    - Death Causer Other
    - Department Type
    - Entry Behavior
    - Ethnicity
    - Ethnicity Other
    - Other Behavior
    - Specify Other Behavior

    2016 form only

    - Exhibit any medical problems?
    - Exhibit any mental health problems?
    - Make suicidal statements?
    - Race
    """
    return [
        "Age At Time Of Death",
        "Agency Address",
        "Agency City",
        "Agency Name",
        "Agency Zip",
        "CDR: CDR Name",
        "City",
        "County",
        "Date of Birth",
        "Date/Time of Custody or Incident",
        "Death Date and Time",
        "Death Location",
        "Death Location Elsewhere",
        "Entry Date Time",
        "Entry Date Time N/A",
        "First Name",
        "Middle Name",
        "Last Name",
        "Suffix",
        "Manner of Death",
        "Manner of Death Description",
        "Means of Death",
        "Means of Death Other",
        "Medical Cause of Death",
        "Medical Examinor/Coroner Evalution?",
        "Medical Treatment",
        "Offense 1",
        "Offense 2",
        "Offense 3",
        "Pre existing medical condition?",
        "Report Date",
        "Sex",
        "Specific Type of Custody/Facility",
        "Street Address",
        "Type of Custody",
        "Type of Offense",
        "Type of Offense, Other",
        "Version Number",
        "Version Type",
        "Were the Charges:",
        "Who caused the death?",
        "form_version",
        "Type of Restraint",
        "Under Restraint",
        "Agency County",
        "Custody Date NA",
        "Death Causer Other",
        "Department Type",
        "Entry Behavior",
        "Ethnicity",
        "Ethnicity Other",
        "Other Behavior",
        "Specify Other Behavior",
        "Exhibit any medical problems?",
        "Exhibit any mental health problems?",
        "Make suicidal statements?",
        "Race",
    ]
