import streamlit as st
import pandas as pd
import numpy as np
import re
import unicodedata
from collections import Counter

st.set_page_config(page_title="Water Usage Dashboard", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .stApp { background-color: #F4F7F5; }
    h1, h2, h3 { color: #2D4A3E !important; font-family: 'Helvetica Neue', sans-serif; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 12px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #FFFFFF; border: 1px solid #D1D8D6;
        border-radius: 8px; padding: 0 24px; color: #4A5D5D; font-weight: 600;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02); transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover { border-color: #7A9E7E; color: #2D4A3E; }
    .stTabs [aria-selected="true"] {
        background-color: #2D4A3E !important; color: #FFFFFF !important; 
        border-color: #2D4A3E !important; box-shadow: 0 4px 10px rgba(45, 74, 62, 0.2);
    }
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
    
    div[data-testid="stMetric"] {
        background-color: #FFFFFF; border: 1px solid #E0E6E4; border-radius: 10px; 
        padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); text-align: center;
    }
    div[data-testid="stMetric"] label { color: #6A7C7C !important; font-weight: 600; font-size: 14px; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #D97736 !important; font-weight: 700; }

    /* Custom tree code block style */
    .tree-box {
        background-color: #FFFFFF; border: 1px solid #E0E6E4; border-radius: 8px; 
        padding: 15px; font-family: monospace; font-size: 13px; line-height: 1.5;
        overflow-x: auto; color: #2D4A3E; white-space: pre-wrap; word-wrap: break-word;
    }
</style>
""", unsafe_allow_html=True)

def clean_text(val):
    if pd.isna(val): return ""
    s = str(val)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def process_headers(df_raw):
    header_rows = 1
    for i in range(min(5, len(df_raw))):
        row_str = " ".join([str(x) for x in df_raw.iloc[i].values if pd.notna(x)]).upper()
        if "ROO1" in row_str or "R001" in row_str or ("RESPONDENT" in row_str and i > 0):
            header_rows = i
            break
    if header_rows == 0: header_rows = 1

    cols = [""] * len(df_raw.columns)
    for i in range(header_rows):
        row_vals = df_raw.iloc[i].fillna("").astype(str).apply(clean_text)
        for j, val in enumerate(row_vals):
            if val: cols[j] = f"{cols[j]} {val}".strip()

    cols = [re.sub(r"\s+", " ", c).strip() for c in cols]
    seen = {}
    for i, c in enumerate(cols):
        if c in seen:
            seen[c] += 1
            cols[i] = f"{c}_{seen[c]}"
        else:
            seen[c] = 1

    df = df_raw.iloc[header_rows:].copy()
    df.columns = cols
    return df.reset_index(drop=True)

def find_col(df, keywords, fallback=None):
    for c in df.columns:
        cu = c.upper()
        if all(k.upper() in cu for k in keywords): return c
    return fallback

def parse_daily_liters(val):
    s = clean_text(val).upper()
    if s == "": return np.nan
    nums = re.findall(r"\d+", s.replace(",", ""))
    if not nums: return np.nan
    if "MORE THAN 300" in s: return 350.0
    if "LESS THAN 50" in s: return 25.0
    if len(nums) >= 2: return (float(nums[0]) + float(nums[1])) / 2.0
    return float(nums[0])

def parse_bill(val):
    s = clean_text(val).upper()
    if s == "" or "NO WATER BILL" in s: return np.nan
    if "ABOVE 1,000" in s or "ABOVE 1000" in s: return 1200.0
    nums = re.findall(r"\d[\d,]*", s)
    nums = [float(n.replace(",", "")) for n in nums]
    if not nums: return np.nan
    if len(nums) >= 2: return (nums[0] + nums[1]) / 2.0
    return nums[0]

def safe_value_counts(df, col_name, limit=None):
    if col_name not in df: return pd.DataFrame(columns=["Label", "Count"])
    vals = [str(v).strip() for v in df[col_name].tolist() if str(v).strip() != "" and str(v).lower() != "nan"]
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    if limit: sorted_counts = sorted_counts[:limit]
    return pd.DataFrame(sorted_counts, columns=["Label", "Count"])

def make_svg_bar(value, max_value, color="#D97736"):
    pct = (value / max_value) * 100 if max_value > 0 else 0
    display_val = f"{value:,.1f}" if isinstance(value, float) else f"{value:,}"
    return f"""
    <div style="display:flex; align-items:center; width:100%; font-family:sans-serif;">
        <div style="flex-grow:1; background-color:#E8EDEA; border-radius:6px; height:20px; margin-right:10px; position:relative;">
            <div style="background-color:{color}; width:{pct}%; height:100%; border-radius:6px;"></div>
        </div>
        <div style="width:60px; text-align:right; font-weight:600; font-size:13px;">{display_val}</div>
    </div>
    """

def render_svg_table(df, label_col, value_col, color="#D97736"):
    if df.empty: return
    max_val = df[value_col].max()
    df_disp = df.copy()
    df_disp[value_col] = df_disp[value_col].apply(lambda x: make_svg_bar(x, max_val, color))
    
    html = "<table style='width:100%; border-collapse:collapse; font-family:sans-serif;'>"
    html += f"<tr style='border-bottom:2px solid #D1D8D6; text-align:left;'><th style='padding:10px; color:#2D4A3E;'>{label_col}</th><th style='padding:10px; color:#2D4A3E; width:60%;'>{value_col}</th></tr>"
    for _, row in df_disp.iterrows():
        html += f"<tr style='border-bottom:1px solid #E8EDEA;'><td style='padding:10px; font-size:14px; font-weight:600; color:#4A5D5D;'>{row[label_col]}</td><td style='padding:10px;'>{row[value_col]}</td></tr>"
    html += "</table>"
    st.html(html)

activity_cols = ["DRINGKING & COOKING", "BATHING", "LAUNDRY", "TOILET FLUSHING", "DISHWASHING", "CLEANING /MOPPING", "WATERING PLANTS", "CAR /VIHICLE WASHING", "ANIMAL CARE"]
activity_labels = {
    "DRINGKING & COOKING": "Drinking & Cooking", "BATHING": "Bathing", "LAUNDRY": "Laundry", 
    "TOILET FLUSHING": "Toilet Flushing", "DISHWASHING": "Dishwashing", "CLEANING /MOPPING": "Cleaning / Mopping",
    "WATERING PLANTS": "Watering Plants", "CAR /VIHICLE WASHING": "Car / Vehicle Washing", "ANIMAL CARE": "Animal Care"
}

st.title("Data Mining-Based Household Water Usage Analysis")
st.markdown("<p style='color: #6A7C7C; font-size: 16px; margin-bottom: 30px;'>Analysis and Visualization of Consumption Patterns in Bliss, Bunawan, Agusan del Sur</p>", unsafe_allow_html=True)

st.sidebar.markdown("### Data Management")
uploaded = st.sidebar.file_uploader("Upload Dataset (CSV or Excel)", type=["csv", "xlsx", "xls"])

if uploaded is None:
    st.info("No dataset loaded. Upload a CSV or Excel file to begin.")
    st.stop()

try:
    if uploaded.name.lower().endswith(".csv"): df_raw = pd.read_csv(uploaded, header=None)
    else: df_raw = pd.read_excel(uploaded, header=None)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

df = process_headers(df_raw)

for c in df.columns:
    if df[c].dtype == object:
        df[c] = df[c].apply(clean_text)

col_family = find_col(df, ["NUMBER OF LIVING"])
col_income = find_col(df, ["MONTHLY", "INCOME"])
col_source = find_col(df, ["PRIMARY SOURCE", "WATER"])
col_daily = find_col(df, ["AVERAGE DAILY HOUSEHOLD WATER"])
col_bill = find_col(df, ["AVERAGE MONTHLY WATER BILL"])
col_conserve = find_col(df, ["PRACTICE WATER CONSERVATION"])
col_practice = find_col(df, ["WHICH OF THE FOLLOWING WATER CONSERVATION"])
col_most = find_col(df, ["WHICH HUSEHOLD ACTIVITY CONSUMES"])
col_shortage = find_col(df, ["EXPERIENCE WATER SHORTAGE"])

if col_daily: df["DailyLiters"] = df[col_daily].apply(parse_daily_liters)
if col_bill: df["MonthlyBill"] = df[col_bill].apply(parse_bill)

if col_daily:
    valid = df["DailyLiters"].dropna()
    if len(valid) >= 6:
        q1, q2 = valid.quantile(0.33), valid.quantile(0.66)
        df["ConsumptionLevel"] = df["DailyLiters"].apply(lambda x: np.nan if pd.isna(x) else ("Low" if x <= q1 else ("Medium" if x <= q2 else "High")))

family_map = {"1-2 PERSON": 1.5, "3-4 PERSON": 3.5, "5-6 PERSON": 5.5, "7-8 PERSON": 7.5, "9 OR MORE": 9.5}
if col_family: df["FamilySizeNum"] = df[col_family].str.upper().map(family_map).astype(float)

income_map = {
    "5000": 5000, "5,000": 5000, "5,000-10,000": 7500, "10,000-15,000": 12500,
    "15,000,20,000": 17500, "15,000-20,000": 17500, "20,000-30,000": 25000, "ABOVE 30,000": 35000
}
if col_income: df["IncomeNum"] = df[col_income].str.upper().map(income_map).astype(float)

tabs = st.tabs(["Consumption Profile", "Clustering (K-Means)", "Classification (Decision Tree)", "Association Rules (Apriori)", "Conservation & Usage Patterns"])

with tabs[0]:
    st.subheader("Household Consumption Profile")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Households", len(df))
    if "DailyLiters" in df:
        c2.metric("Mean Daily Use", f"{df['DailyLiters'].mean():.1f} L")
        c3.metric("Median Daily Use", f"{df['DailyLiters'].median():.1f} L")
    if "MonthlyBill" in df: c4.metric("Mean Monthly Bill", f"₱ {df['MonthlyBill'].mean():.0f}")

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Consumption Level Distribution")
        if "ConsumptionLevel" in df and df["ConsumptionLevel"].notna().any():
            items = safe_value_counts(df, "ConsumptionLevel")
            items = items.set_index("Label").reindex(["Low", "Medium", "High"]).fillna(0).reset_index()
            render_svg_table(items, "Label", "Count", "#D97736")
    with col_b:
        st.markdown("### Households by Water Source")
        if col_source: 
            items = safe_value_counts(df, col_source)
            render_svg_table(items, "Label", "Count", "#4A7C59")

    st.markdown("---")
    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown("### Mean Daily Use by Family Size")
        if "FamilySizeNum" in df and df["FamilySizeNum"].notna().any():
            grp = df.dropna(subset=["FamilySizeNum", "DailyLiters"]).groupby("FamilySizeNum")["DailyLiters"].mean().reset_index()
            grp["Label"] = grp["FamilySizeNum"].astype(str) + " Persons"
            render_svg_table(grp[["Label", "DailyLiters"]], "Label", "DailyLiters", "#2D4A3E")
    with col_d:
        st.markdown("### Mean Daily Use by Income Band")
        if "IncomeNum" in df and df["IncomeNum"].notna().any():
            gi = df.dropna(subset=["IncomeNum", "DailyLiters"]).groupby("IncomeNum")["DailyLiters"].mean().reset_index()
            gi["Label"] = "₱ " + gi["IncomeNum"].astype(int).astype(str)
            render_svg_table(gi[["Label", "DailyLiters"]], "Label", "DailyLiters", "#7A9E7E")

with tabs[1]:
    st.subheader("K-Means Clustering Analysis")
    feature_cols = [c for c in ["FamilySizeNum", "IncomeNum", "DailyLiters", "MonthlyBill"] if c in df and df[c].notna().any()]
    cluster_ready = df.dropna(subset=feature_cols).copy() if feature_cols else pd.DataFrame()

    if len(cluster_ready) >= 8 and len(feature_cols) >= 2:
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score, davies_bouldin_score
        X = cluster_ready[feature_cols].to_numpy(dtype=np.float64)
        Xs = StandardScaler().fit_transform(X)
        max_k = min(6, len(cluster_ready) - 1)
        ks = list(range(2, max_k + 1))
        wcss, sil, dbi = [], [], []
        for k in ks:
            km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xs)
            wcss.append(km.inertia_)
            sil.append(silhouette_score(Xs, km.labels_))
            dbi.append(davies_bouldin_score(Xs, km.labels_))
            
        metrics_df = pd.DataFrame({"k": ks, "WCSS": wcss, "Silhouette": sil, "DaviesBouldin": dbi})
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Elbow Method (WCSS)")
            m_df = metrics_df.copy()
            m_df["Label"] = "k=" + m_df["k"].astype(str)
            render_svg_table(m_df[["Label", "WCSS"]], "Label", "WCSS", "#D97736")
            st.dataframe(metrics_df.set_index("k"), use_container_width=True)
        with c2:
            st.markdown("### Silhouette Score")
            m_df = metrics_df.copy()
            m_df["Label"] = "k=" + m_df["k"].astype(str)
            render_svg_table(m_df[["Label", "Silhouette"]], "Label", "Silhouette", "#2D4A3E")
            
        best_k = ks[int(np.argmax(sil))]
        st.info(f"Optimal K selected by maximum Silhouette Score: **{best_k} clusters** (Davies-Bouldin: {dbi[ks.index(best_k)]:.3f})")
        
        km = KMeans(n_clusters=best_k, n_init=10, random_state=42).fit(Xs)
        cluster_ready["Cluster"] = km.labels_
        prof = cluster_ready.groupby("Cluster")[feature_cols].mean().round(2)
        prof["Households"] = cluster_ready.groupby("Cluster").size()
        st.markdown("### Cluster Profiles (Means)")
        st.dataframe(prof, use_container_width=True)

with tabs[2]:
    st.subheader("Decision Tree Classification")
    if "ConsumptionLevel" in df and df["ConsumptionLevel"].notna().sum() >= 12:
        from sklearn.tree import DecisionTreeClassifier, export_text
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
        feat = [c for c in ["FamilySizeNum", "IncomeNum", "MonthlyBill"] if c in df and df[c].notna().any()]
        tree_df = df.dropna(subset=feat + ["ConsumptionLevel"]).copy()
        
        if len(tree_df) >= 12 and feat:
            X = tree_df[feat].to_numpy(dtype=np.float64)
            y = tree_df["ConsumptionLevel"].to_numpy(dtype=str)
            Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
            clf = DecisionTreeClassifier(max_depth=4, random_state=42).fit(Xtr, ytr)
            pred = clf.predict(Xte)
            
            acc = accuracy_score(yte, pred)
            p, r, f1, _ = precision_recall_fscore_support(yte, pred, average="macro", zero_division=0)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Accuracy", f"{acc:.3f}"); c2.metric("Precision", f"{p:.3f}")
            c3.metric("Recall", f"{r:.3f}"); c4.metric("F1-Score", f"{f1:.3f}")
            
            st.markdown("---")
            col_cm, col_rules = st.columns([1, 1.5])
            with col_cm:
                st.markdown("### Confusion Matrix")
                labels = sorted(set(yte) | set(pred))
                cm = confusion_matrix(yte, pred, labels=labels)
                cm_df = pd.DataFrame(cm, index=[f"Actual {l}" for l in labels], columns=[f"Pred {l}" for l in labels])
                
                # Display as a styled heatmap table
                st.dataframe(
                    cm_df.style.background_gradient(cmap="Oranges", axis=None)
                    .format("{:,}"),
                    use_container_width=True
                )
            with col_rules:
                st.markdown("### Decision Tree Rules")
                # Render rules in a clean custom box with preserved whitespace
                rules_text = export_text(clf, feature_names=feat, spacing=3)
                st.markdown(f"<div class='tree-box'><pre>{rules_text}</pre></div>", unsafe_allow_html=True)

with tabs[3]:
    st.subheader("Apriori Association Rules")
    try:
        from mlxtend.frequent_patterns import apriori, association_rules
        arm_cols = []
        if col_family: arm_cols.append(col_family)
        if col_income: arm_cols.append(col_income)
        if col_source: arm_cols.append(col_source)
        if "ConsumptionLevel" in df and df["ConsumptionLevel"].notna().any(): arm_cols.append("ConsumptionLevel")
        arm_df = df[arm_cols].dropna().copy()
        
        if len(arm_df) >= 10 and len(arm_cols) >= 2:
            trans = pd.get_dummies(arm_df.astype(str))
            trans = trans.loc[:, trans.sum() / len(trans) >= 0.10]
            if trans.shape[1] >= 3:
                freq = apriori(trans, min_support=0.10, use_colnames=True)
                if len(freq) > 0:
                    rules = association_rules(freq, metric="confidence", min_threshold=0.60)
                    rules = rules[rules["lift"] > 1.0].sort_values("lift", ascending=False)
                    if len(rules) > 0:
                        show = rules[["antecedents", "consequents", "support", "confidence", "lift"]].copy()
                        show["antecedents"] = show["antecedents"].apply(lambda s: ", ".join(sorted(s)))
                        show["consequents"] = show["consequents"].apply(lambda s: ", ".join(sorted(s)))
                        
                        st.markdown("### Discovered Rules (Support >= 0.10, Confidence >= 0.60, Lift > 1.0)")
                        st.dataframe(show.reset_index(drop=True), use_container_width=True)
                        
                        top = show.head(15).copy()
                        top["Rule"] = top["antecedents"] + " -> " + top["consequents"]
                        render_svg_table(top[["Rule", "lift"]], "Rule", "lift", "#4A7C59")
    except ImportError: st.write("Association rule library unavailable.")

with tabs[4]:
    st.subheader("Conservation & Usage Patterns")
    act_present = [c for c in df.columns if any(act in c.upper() for act in activity_cols)]
    
    col_piv, col_most = st.columns(2)
    with col_piv:
        if act_present:
            st.markdown("### Activity Frequency Profile")
            rows = []
            for c in act_present:
                label = next((act_label for act_key, act_label in activity_labels.items() if act_key in c.upper()), c)
                for k, v in safe_value_counts(df, c).values.tolist():
                    if str(k).upper() in ["DAILY", "WEEKLY", "MONTHLY", "RARELY", "NEVER"]:
                        rows.append({"Activity": label, "Frequency": str(k).upper(), "Households": v})
            af = pd.DataFrame(rows)
            if not af.empty:
                pivot = af.pivot_table(index="Activity", columns="Frequency", values="Households", aggfunc="sum").fillna(0)
                order = [x for x in ["DAILY", "WEEKLY", "MONTHLY", "RARELY", "NEVER"] if x in pivot.columns]
                pivot = pivot[order]
                st.dataframe(pivot, use_container_width=True)
                
                flat_counts = []
                for activity in pivot.index:
                    for freq in order:
                        if pivot.loc[activity, freq] > 0:
                            flat_counts.append({"Label": f"{activity} ({freq})", "Count": pivot.loc[activity, freq]})
                flat_df = pd.DataFrame(flat_counts)
                render_svg_table(flat_df, "Label", "Count", "#D97736")

    with col_most:
        if col_most:
            st.markdown("### Activity Consuming Most Water")
            items = safe_value_counts(df, col_most)
            render_svg_table(items, "Label", "Count", "#D97736")
            
    st.markdown("---")
    col_cons, col_prac = st.columns(2)
    with col_cons:
        if col_conserve:
            st.markdown("### Conservation Practice Adoption")
            items = safe_value_counts(df, col_conserve)
            render_svg_table(items, "Label", "Count", "#2D4A3E")
    with col_prac:
        if col_practice:
            st.markdown("### Top Conservation Methods Applied")
            items = safe_value_counts(df, col_practice, limit=10)
            render_svg_table(items, "Label", "Count", "#7A9E7E")
            
    if col_shortage and col_source:
        st.markdown("---")
        st.markdown("### Water Shortage Experience by Source")
        ct = pd.crosstab(df[col_source].astype(str), df[col_shortage].astype(str))
        st.dataframe(ct, use_container_width=True)
        
        flat_ct = []
        for source in ct.index:
            for resp in ct.columns:
                if ct.loc[source, resp] > 0:
                    flat_ct.append({"Label": f"{source} ({resp})", "Count": ct.loc[source, resp]})
        flat_ct_df = pd.DataFrame(flat_ct)
        render_svg_table(flat_ct_df, "Label", "Count", "#4A7C59")
