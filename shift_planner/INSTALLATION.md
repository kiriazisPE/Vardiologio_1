# 🚀 Installation & Quick Start Guide

## Prerequisites

- **Python**: 3.9 or higher
- **pip**: Latest version
- **Git**: For cloning (optional)

## Installation Steps

### 1. Prepare Environment

```bash
# Navigate to project directory
cd "c:\Users\akiri\Desktop\Other Prtojects\shift_planner"

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat
# Linux/Mac:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt

# Verify installation
pip list
```

Expected packages:
- streamlit 1.40.0
- plotly 5.24.0
- pandas 2.2.2
- numpy 2.0.0
- openpyxl 3.1.5
- streamlit-authenticator 0.4.1
- pulp 2.7.0
- PyYAML 6.0.2
- Pillow 10.4.0
- python-dotenv 1.0.1
- python-dateutil 2.9.0

### 3. Configure Environment

```bash
# Create .env file
echo "AUTH_ENABLED=false
DEV_AUTH_FALLBACK=true
APP_ENV=dev
DB_FILE=shifts.db
SERVER_PORT=8501
SESSION_TTL_MIN=240
TZ=Europe/Athens
LOG_LEVEL=INFO" > .env
```

### 4. Run the Application

```bash
streamlit run main.py
```

The application will open automatically in your default browser at:
```
http://localhost:8501
```

## Quick Test Drive

### Test Scenario 1: Demo Mode (5 minutes)

1. **Open Application**
   - Navigate to http://localhost:8501

2. **Welcome Tour**
   - On first launch, you'll see the welcome dialog
   - Click "Ξεκινήστε την Ξενάγηση" or "Παράλειψη"

3. **Select Demo Company**
   - Click "Demo Coffee" or create a new company

4. **Load Demo Data**
   - Go to "👥 Υπάλληλοι" page
   - Click "✨ Συμπλήρωση demo δεδομένων"
   - This creates 3 sample employees

5. **Generate Schedule**
   - Go to "📅 Πρόγραμμα" page
   - Select "Εβδομαδιαίο" scope
   - Click "🛠 Δημιουργία"
   - View auto-generated schedule!

6. **Explore Analytics**
   - Click "📊 Αναλυτικά" button
   - Browse all visualization tabs
   - Check workload distribution

7. **Try Calendar View**
   - Click "📅 Ημερολόγιο" button
   - Navigate through months
   - Click on dates for details

8. **Export Schedule**
   - Click "📥 Εξαγωγή" button
   - Download Excel file
   - Open and review multi-sheet workbook

### Test Scenario 2: Create Real Schedule (15 minutes)

1. **Create Your Company**
   - Go to "🔍 Επιλογή" page
   - Enter company name
   - Click "Δημιουργία"

2. **Configure Settings**
   - Go to "🏢 Επιχείρηση" page
   - Set work model (5/6/7 days)
   - Add custom shifts if needed
   - Define roles (Cashier, Server, etc.)
   - Configure priority and requirements
   - Set labor rules (max hours, rest time, etc.)
   - Click "💾 Αποθήκευση Ρυθμίσεων"

3. **Add Employees**
   - Go to "👥 Υπάλληλοι" page
   - Fill form:
     - Name: "John Doe"
     - Roles: Select applicable roles
     - Availability: Which shifts they can work
   - Click "➕ Προσθήκη"
   - Repeat for at least 3-5 employees

4. **Generate Schedule**
   - Go to "📅 Πρόγραμμα" page
   - Choose date range (weekly or monthly)
   - Click "🛠 Δημιουργία"
   - Review generated schedule
   - Check for violations (should be minimal)

5. **Manual Adjustments**
   - Scroll to "Visual Builder" section
   - Use dropdowns to adjust assignments
   - Click "💾 Αποθήκευση εβδομάδας"

6. **Review Analytics**
   - Click "📊 Αναλυτικά"
   - Check hours distribution (should be balanced)
   - Review shift allocation
   - Verify role coverage

## Troubleshooting

### Issue: Module not found errors

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Issue: Port already in use

```bash
# Use different port
streamlit run main.py --server.port=8502
```

### Issue: Database locked

```bash
# Close all instances and delete lock file
del shifts.db-wal
del shifts.db-shm
```

### Issue: Plotly charts not showing

```bash
# Clear cache
streamlit cache clear
# Restart application
```

### Issue: Authentication errors (if enabled)

```bash
# Disable authentication for testing
echo "AUTH_ENABLED=false" >> .env
```

## Feature Checklist

Test all major features:

- [ ] Company management
  - [ ] Create company
  - [ ] Configure work model
  - [ ] Add custom shifts
  - [ ] Define roles
  - [ ] Set rules

- [ ] Employee management
  - [ ] Add employees
  - [ ] Edit employee details
  - [ ] Delete employees
  - [ ] Set availability

- [ ] Schedule generation
  - [ ] Automatic weekly schedule
  - [ ] Automatic monthly schedule
  - [ ] Manual adjustments in visual builder
  - [ ] Save to database

- [ ] Analytics
  - [ ] View hours distribution chart
  - [ ] View shift distribution pie
  - [ ] View timeline/Gantt
  - [ ] View coverage heatmap
  - [ ] Check workload balance

- [ ] Calendar views
  - [ ] Monthly calendar
  - [ ] Weekly timeline
  - [ ] Day details dialog

- [ ] Export/Import
  - [ ] Export to Excel
  - [ ] Export to CSV
  - [ ] Import from file
  - [ ] Validate imported data

- [ ] Shift swaps
  - [ ] Create swap request
  - [ ] Approve request
  - [ ] Reject request
  - [ ] View history

- [ ] UI/UX
  - [ ] Toggle dark/light theme
  - [ ] View notifications
  - [ ] Complete onboarding tour
  - [ ] Access help panel

## Performance Tips

1. **Use Fragments**: Most features already use `@st.fragment` for fast updates

2. **Database**: SQLite in WAL mode handles concurrent access well

3. **Large Datasets**: For 100+ employees, consider:
   - Weekly scheduling instead of monthly
   - Pagination in employee lists
   - Date range filters

4. **Browser**: Chrome/Edge recommended for best performance

## Next Steps

After successful installation:

1. **Read Documentation**
   - See `DOCUMENTATION.md` for complete guide
   - Review `MODERNIZATION_SUMMARY.md` for feature details

2. **Customize**
   - Add your company data
   - Configure rules to match your needs
   - Customize shifts and roles

3. **Explore Advanced Features**
   - Try MILP optimization (auto-enabled if PuLP installed)
   - Use auto-fix for violation resolution
   - Set up shift swap workflows

4. **Production Deployment**
   - Enable authentication
   - Use Docker for deployment
   - Set up backups
   - Configure SSL/HTTPS

## Support

If you encounter issues:

1. Check console for error messages
2. Review `LOG_LEVEL=DEBUG` in .env for detailed logs
3. Examine `DOCUMENTATION.md` troubleshooting section
4. Check database file permissions

## Success Indicators

✅ Application starts without errors
✅ All pages load correctly
✅ Demo data creates successfully
✅ Schedule generates without violations
✅ Charts render properly
✅ Excel export downloads
✅ Theme toggle works
✅ No console errors

---

**Congratulations!** 🎉 Your modern Shift Planner Pro is ready to use!

Enjoy all the new features and capabilities.
