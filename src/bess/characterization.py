"""Excel characterization loader for OCV/SoC and 1RC parameters."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bess.lookup_table import OCVR1C1LookupTable

__all__ = ["load_ocv_r1c1_from_excel"]


def load_ocv_r1c1_from_excel(
    path: str | Path,
    q_nom_ah: float,
    sheet_name: str | int = 0,
    soh_column: str = "SOH",
    ah_column: str = "Ah",
    ocv_column: str = "OCV",
    r1_column: str = "R1",
    c1_column: str = "C1",
) -> OCVR1C1LookupTable:
    """Load OCV/R1/C1 lookup data from Excel and return OCVR1C1LookupTable.

    Notes:
    - SoC is always reconstructed from Ah using `soc = 1 - Ah/q_nom_ah`.
    - Any SOC/SOH columns present in Excel are ignored in this flow.
    """
    excel_path = Path(path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    q_nom = float(q_nom_ah)
    if q_nom <= 0.0:
        raise ValueError(f"q_nom_ah must be > 0, got {q_nom_ah!r}.")

    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")
    except ValueError as exc:
        raise ValueError(
            f"Failed to read sheet {sheet_name!r} from '{excel_path.name}'."
        ) from exc

    required_columns = [ah_column, ocv_column, r1_column, c1_column]
    for column_name in required_columns:
        if column_name not in df.columns:
            raise KeyError(
                f"Missing required column '{column_name}' in '{excel_path.name}' "
                f"(sheet={sheet_name!r}). Available columns: {list(df.columns)!r}"
            )

    # SOH/SOC columns from Excel are intentionally ignored in this flow.
    _ = soh_column
    selected = df[[ah_column, ocv_column, r1_column, c1_column]].copy()
    for column_name in (ah_column, ocv_column, r1_column, c1_column):
        selected[column_name] = pd.to_numeric(selected[column_name], errors="coerce")

    selected = selected.dropna(subset=[ah_column, ocv_column, r1_column, c1_column])
    if selected.empty:
        raise ValueError(
            f"No valid rows after numeric conversion/dropna in '{excel_path.name}' "
            f"(sheet={sheet_name!r}) for columns: "
            f"{[ah_column, ocv_column, r1_column, c1_column]!r}."
        )

    selected["soc"] = 1.0 - (selected[ah_column] / q_nom)
    selected = selected.dropna(subset=["soc"])
    selected = selected[(selected["soc"] >= 0.0) & (selected["soc"] <= 1.0)]
    selected = selected.sort_values("soc", ascending=True)
    selected = selected.drop_duplicates(subset=["soc"], keep="first")

    if selected.empty:
        raise ValueError(
            "No data rows available after SoC reconstruction, [0,1] filtering, "
            "sorting and duplicate removal."
        )

    soc_data = selected["soc"].to_numpy(dtype=float)
    ocv_data = selected[ocv_column].to_numpy(dtype=float)
    r1_data = selected[r1_column].to_numpy(dtype=float)
    c1_data = selected[c1_column].to_numpy(dtype=float)

    n = len(soc_data)
    if not (len(ocv_data) == n and len(r1_data) == n and len(c1_data) == n):
        raise ValueError(
            "Length mismatch in processed arrays: "
            f"soc={len(soc_data)}, ocv={len(ocv_data)}, r1={len(r1_data)}, c1={len(c1_data)}."
        )

    if n < 2:
        raise ValueError(f"At least 2 unique SoC points are required, got {n}.")

    if not (soc_data[1:] > soc_data[:-1]).all():
        raise ValueError("soc_data must be strictly increasing after preprocessing.")

    return OCVR1C1LookupTable(
        soc_data=soc_data,
        ocv_data=ocv_data,
        r1_data=r1_data,
        c1_data=c1_data,
        source_reference=f"Cargado desde {excel_path.name}",
    )
