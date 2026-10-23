"""Read and write your job tracker, whether it's an Excel file, a CSV file, or a Google Sheet.

Which tracker to use comes from config/tracker_map.json (setup_wizard.py fills this in):

  "source": {"type": "excel", "path": "tracker/my_job_tracker.xlsx"}
  "source": {"type": "csv", "path": "tracker/my_job_tracker.csv"}
  "source": {"type": "google_sheets", "url": "https://docs.google.com/spreadsheets/d/...",
             "credentials": "config/google_service_account.json"}

"sheet" in the same file is the tab name (null means the first tab), and "columns" names your headers.
A tracker given on the command line (a file path or a Google Sheets link) is used instead of the config.

Excel needs openpyxl (pip3 install openpyxl). Google Sheets needs gspread (pip3 install gspread) and a
service account key; README.md, "Using Google Sheets", walks through it. CSV needs nothing extra.
"""
import csv, datetime, json, re, shutil, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = ROOT / "config"
DEFAULT_EXCEL = "tracker/my_job_tracker.xlsx"
DEFAULT_CREDENTIALS = "config/google_service_account.json"
ASSISTANT_NOTES = "Assistant Notes"
TEMPLATE_COLUMNS = ["Date Added", "Company", "Job Title", "Location", "Work Type", "Salary Range", "Salary Min",
                    "Source", "Link", "Date Applied", "Status", "Resume Match", "Fit Score", "Notes", ASSISTANT_NOTES]
HYPERLINK = re.compile(r'=HYPERLINK\(\s*"([^"]*)"\s*[,;]\s*"(.*)"\s*\)\s*$', re.I)
SHEETS_URL = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")

def load_map():
    return json.loads((CFG / "tracker_map.json").read_text())

def save_map(tmap):
    (CFG / "tracker_map.json").write_text(json.dumps(tmap, indent=1, ensure_ascii=False) + "\n")

def resolve(p):
    p = pathlib.Path(p).expanduser()
    return p if p.is_absolute() else ROOT / p

def is_sheets_link(s):
    return bool(SHEETS_URL.search(str(s or "")))

def sheet_key(url_or_id):
    """The spreadsheet ID from a Google Sheets link (or the ID itself)."""
    s = str(url_or_id or "").strip()
    m = SHEETS_URL.search(s)
    if m: return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{25,}", s): return s
    sys.exit(f"That doesn't look like a Google Sheets link: {s}\n"
             "Copy the address from your browser while the sheet is open (it contains /spreadsheets/d/).")

def describe_source(src):
    t = (src or {}).get("type")
    if t == "google_sheets": return f"Google Sheet {src.get('url', '')}"
    return f"{'CSV file' if t == 'csv' else 'Excel file'} {src.get('path', DEFAULT_EXCEL) if src else DEFAULT_EXCEL}"

def open_tracker(arg=None, tmap=None):
    """The tracker named on the command line, or the one in config/tracker_map.json."""
    tmap = tmap or load_map()
    tab, cols = tmap.get("sheet"), tmap["columns"]
    if arg:
        if is_sheets_link(arg):
            creds = (tmap.get("source") or {}).get("credentials", DEFAULT_CREDENTIALS)
            return GoogleSheetsTracker(arg, tab, cols, creds)
        path = resolve(arg)
        return CsvTracker(path, tab, cols) if path.suffix.lower() == ".csv" else ExcelTracker(path, tab, cols)
    src = tmap.get("source") or {"type": "excel", "path": DEFAULT_EXCEL}
    t = src.get("type", "excel")
    if t == "google_sheets":
        return GoogleSheetsTracker(src.get("url"), tab, cols, src.get("credentials", DEFAULT_CREDENTIALS))
    if t == "csv":
        return CsvTracker(resolve(src.get("path", "tracker/my_job_tracker.csv")), tab, cols)
    return ExcelTracker(resolve(src.get("path", DEFAULT_EXCEL)), tab, cols)

def find_header(grid, cols):
    """(row index, {lowercase header: column index}) for the first of 10 rows with the company and title headers."""
    company, title = cols["company"].strip().lower(), cols["title"].strip().lower()
    for i, row in enumerate(grid[:10]):
        names = {}
        for j, v in enumerate(row):
            n = str(v if v is not None else "").strip().lower()
            if n and n not in names: names[n] = j
        if company in names and title in names: return i, names
    sys.exit(f"Could not find the '{cols['company']}' and '{cols['title']}' headers in the first 10 rows of your "
             "tracker. Check the column names (and the tab name, \"sheet\") in config/tracker_map.json.")

class Tracker:
    kind = "tracker"
    can_write = False

    def __init__(self, tab, cols):
        self.tab, self.cols = tab, cols

    def grid(self):
        """Every row as a list of (value, link) pairs."""
        raise NotImplementedError

    def field_header(self, field):
        """Header name for a field: company/title/status/link come from tracker_map.json, others are template names."""
        return self.cols.get(field, field)

    def existing(self, values):
        """Header row index, header names, last row index with a job, and the company|title keys already there."""
        from common import norm_co, norm_title
        hr, names = find_header(values, self.cols)
        c_co, c_ti = names[self.cols["company"].lower()], names[self.cols["title"].lower()]
        last, keys = hr, set()
        for i in range(hr + 1, len(values)):
            row = values[i]
            co = row[c_co] if c_co < len(row) else None
            ti = row[c_ti] if c_ti < len(row) else None
            if co not in (None, "") or ti not in (None, ""):
                last = i
                keys.add(norm_co(str(co or "")) + "|" + norm_title(str(ti or "")))
        return hr, names, last, keys

class CsvTracker(Tracker):
    kind = "CSV file"

    def __init__(self, path, tab, cols):
        super().__init__(tab, cols); self.path = path
        self.label = str(path)

    def grid(self):
        if not self.path.exists(): sys.exit(f"Tracker not found: {self.path}")
        with open(self.path, newline="", encoding="utf-8-sig") as f:
            return [[(v, None) for v in row] for row in csv.reader(f)]

class ExcelTracker(Tracker):
    kind = "Excel file"
    can_write = True

    def __init__(self, path, tab, cols):
        super().__init__(tab, cols); self.path = path
        self.label = str(path)

    def _open(self):
        if not self.path.exists(): sys.exit(f"Tracker not found: {self.path}")
        try:
            import openpyxl
        except ImportError:
            sys.exit("Reading Excel files needs one package: pip3 install openpyxl")
        wb = openpyxl.load_workbook(self.path)
        if self.tab and self.tab not in wb.sheetnames:
            sys.exit(f"No tab named '{self.tab}' in {self.path.name}. Tabs: {', '.join(wb.sheetnames)}")
        return wb, (wb[self.tab] if self.tab else wb.worksheets[0])

    def grid(self):
        _, ws = self._open()
        return [[(c.value, c.hyperlink.target if c.hyperlink else None) for c in row] for row in ws.iter_rows()]

    def existing_keys(self):
        _, ws = self._open()
        return self.existing([[c.value for c in row] for row in ws.iter_rows()])[3]

    def backup(self):
        dest = self.path.parent / "backups" / f"{self.path.stem}_{datetime.datetime.now():%Y%m%d-%H%M%S}{self.path.suffix}"
        dest.parent.mkdir(exist_ok=True); shutil.copy(self.path, dest)
        return dest

    def append(self, records):
        """Add records ({field or header name: value}) below the last job. 'link' becomes a clickable "Link"."""
        import openpyxl
        wb, ws = self._open()
        hr, names, last, _ = self.existing([[c.value for c in row] for row in ws.iter_rows()])
        col = lambda h: names.get(str(h).lower())  # 0-based
        if col(ASSISTANT_NOTES) is None:
            c = max(names.values()) + 1
            h = ws.cell(hr + 1, c + 1, ASSISTANT_NOTES); h._style = ws.cell(hr + 1, c)._style
            ws.column_dimensions[openpyxl.utils.get_column_letter(c + 1)].width = 50
            names[ASSISTANT_NOTES.lower()] = c
        for i, rec in enumerate(records, 1):
            r = last + 1 + i  # 1-based row
            for field, v in rec.items():
                c = col(self.field_header(field))
                if c is None or v in (None, ""): continue
                cell = ws.cell(r, c + 1)
                if field == "link":
                    cell.value = "Link"; cell.hyperlink = v
                else:
                    cell.value = v
                    if isinstance(v, datetime.date): cell.number_format = "mm/dd/yyyy"
        wb.save(self.path)

class GoogleSheetsTracker(Tracker):
    kind = "Google Sheet"
    can_write = True

    def __init__(self, url, tab, cols, credentials=DEFAULT_CREDENTIALS):
        super().__init__(tab, cols)
        if not url: sys.exit("No Google Sheets link in config/tracker_map.json. Run: python3 setup_wizard.py --tracker")
        self.key = sheet_key(url)
        self.label = f"https://docs.google.com/spreadsheets/d/{self.key}"
        self.creds = resolve(credentials or DEFAULT_CREDENTIALS)
        self._ws = None

    def service_email(self):
        try: return json.loads(self.creds.read_text()).get("client_email")
        except Exception: return None

    def worksheet(self):
        if self._ws: return self._ws
        try:
            import gspread
        except ImportError:
            sys.exit("Google Sheets needs one package: pip3 install gspread")
        if not self.creds.exists():
            sys.exit(f"Google service account key not found: {self.creds}\n"
                     "See README.md, \"Using Google Sheets\", step 1, then save the key file there.")
        email = self.service_email() or "the client_email in your key file"
        try:
            sh = gspread.service_account(filename=str(self.creds)).open_by_key(self.key)
            self._ws = sh.worksheet(self.tab) if self.tab else sh.sheet1
        except gspread.exceptions.WorksheetNotFound:
            tabs = ", ".join(w.title for w in sh.worksheets())
            sys.exit(f"No tab named '{self.tab}' in the Google Sheet. Tabs: {tabs}")
        except gspread.exceptions.SpreadsheetNotFound:
            sys.exit(f"Couldn't open the Google Sheet. Share it with {email} as an Editor, then try again.")
        except gspread.exceptions.APIError as e:
            msg = str(e)
            if "SERVICE_DISABLED" in msg or "has not been used" in msg:
                sys.exit("The Google Sheets API isn't turned on for your Google Cloud project yet. "
                         "See README.md, \"Using Google Sheets\", step 1.")
            if "PERMISSION_DENIED" in msg or "403" in msg or "404" in msg:
                sys.exit(f"Couldn't open the Google Sheet. Share it with {email} as an Editor, then try again.")
            raise
        return self._ws

    def values(self, formulas=True):
        opt = "FORMULA" if formulas else "FORMATTED_VALUE"
        return self.worksheet().get_values(value_render_option=opt)

    def grid(self):
        # Formulas, so =HYPERLINK("url", "text") cells keep their URL (import reads the link from the formula).
        return [[(v, None) for v in row] for row in self.values()]

    def existing_keys(self):
        return self.existing(self.values(formulas=False))[3]

    def backup(self):
        """A CSV snapshot in tracker/backups/ (Google also keeps version history: File > Version history)."""
        dest = ROOT / "tracker" / "backups" / f"google_sheet_{datetime.datetime.now():%Y%m%d-%H%M%S}.csv"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(self.values(formulas=False))
        return dest

    def write_headers(self, headers=TEMPLATE_COLUMNS):
        """Put the template's column headers in row 1 of an empty tab."""
        ws = self.worksheet()
        if ws.col_count < len(headers): ws.add_cols(len(headers) - ws.col_count)
        ws.update(values=[headers], range_name="A1", value_input_option="RAW")

    def append(self, records):
        from gspread.utils import rowcol_to_a1
        ws = self.worksheet()
        values = self.values(formulas=False)
        hr, names, last, _ = self.existing(values)
        col = lambda h: names.get(str(h).lower())
        raw, entered = [], []  # text and numbers as-is; dates and links interpreted by Sheets
        if col(ASSISTANT_NOTES) is None:
            c = max(names.values()) + 1
            if c + 1 > ws.col_count: ws.add_cols(c + 1 - ws.col_count)
            raw.append({"range": rowcol_to_a1(hr + 1, c + 1), "values": [[ASSISTANT_NOTES]]})
            names[ASSISTANT_NOTES.lower()] = c
        need = last + 1 + len(records)
        if need > ws.row_count: ws.add_rows(need - ws.row_count)
        for i, rec in enumerate(records, 1):
            r = last + 1 + i
            for field, v in rec.items():
                c = col(self.field_header(field))
                if c is None or v in (None, ""): continue
                a1 = rowcol_to_a1(r, c + 1)
                if field == "link":
                    entered.append({"range": a1, "values": [['=HYPERLINK("' + str(v).replace('"', '""') + '", "Link")']]})
                elif isinstance(v, datetime.date):
                    entered.append({"range": a1, "values": [[v.strftime("%m/%d/%Y")]]})
                else:
                    raw.append({"range": a1, "values": [[v]]})
        if raw: ws.batch_update(raw, value_input_option="RAW")
        if entered: ws.batch_update(entered, value_input_option="USER_ENTERED")
