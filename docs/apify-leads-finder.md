✨Leads Finder — Effortless Data Extraction
A cost-effective alternative to ZoomInfo, Lusha & Apollo. Get verified B2B emails, LinkedIn profiles, and rich firmographics at scale.

🚀 What this actor does
Leads Finder generates targeted B2B contact lists using advanced filters (job title, Location/City, industry, tech stack, revenue, funding, etc.) and returns verified emails, mobile numbers (paying plans only), LinkedIn URLs, and detailed company data — ready for CRM or outreach. Free plan note: Users on the free Apify plan can fetch up to 100 leads/run.

Support: codecrafter70@gmail.com

🧭 Quick start (UI)
Open the actor, set 📁 File name / Run label (optional).
Choose your filters (e.g., 👔 Job Title = "Marketing Manager", 🌍 Location = "United States", 🏭 Industry = "SaaS").
Set #️⃣ Number of leads to fetch (default 50,000; leave empty to fetch all that match).
Click Run. When finished, download results from the Dataset tab or use the Overview table.
Location vs City: Use Location for a region/country/state. To target a single city, leave Location empty and use City only. (Same logic for the Exclude fields.)

🧩 Input schema (fields you can use)
Fields accept arrays unless noted.

General
fetch_count (integer, default 50000) — Max leads to fetch. Leave empty to fetch all matches.
file_name (string) — Custom run label / export name.
People targeting
contact_job_title / contact_not_job_title — Include/Exclude titles ("realtor", "software developer", "teacher", …).
seniority_level — Founder, Owner, C-Level, Director, VP, Head, Manager, Senior, Entry, Trainee.
functional_level — C-Level, Finance, Product, Engineering, Design, HR, IT, Legal, Marketing, Operations, Sales, Support.
Location (Include)
contact_location — Region/Country/State (e.g., EMEA, United States, California, US).
contact_city — One or more cities (use this instead of Location when you want city-level targeting only).
Location (Exclude)
contact_not_location — Region/Country/State to exclude.
contact_not_city — One or more cities to exclude.
Email quality
email_status — validated, not_validated, unknown (prefill: validated)
Company targeting
company_domain — Limit to specific domains (e.g., google.com, https://apple.com).
size — 0–1, 2–10, 11–20, 21–50, 51–100, 101–200, 201–500, 501–1000, 1001–2000, 2001–5000, 10000+
company_industry / company_not_industry — Include/Exclude industries.
company_keywords / company_not_keywords — Include/Exclude free-text keywords.
min_revenue, max_revenue — Revenue bands (100K → 10B).
funding — Seed, Angel, Series A…F, Venture, Debt, Convertible, PE, Other.
📤 Output schema (what you get)
Results are written to the run's Dataset and rendered in the Overview table with these columns:

Person

first_name, last_name, full_name, job_title, headline, functional_level, seniority_level
email (verified when available)
mobile_number (available for paying Apify plan users only)
personal_email
linkedin (profile link)
city, state, country
Company

company_name, company_domain, company_website (link), company_linkedin (link), company_linkedin_uid
company_size, industry, company_description
company_annual_revenue, company_annual_revenue_clean
company_total_funding, company_total_funding_clean
company_founded_year, company_phone
company_street_address, company_city, company_state, company_country, company_postal_code, company_full_address
company_market_cap (if public)
Context

keywords, company_technologies
🔎 Examples
Example 1 — US SaaS marketing leaders
contact_job_title: ["Head of Marketing","VP Marketing","CMO"]
functional_level: ["marketing"]
contact_location: ["united states"]
company_industry: ["computer software","internet","information technology & services","marketing & advertising","saas"]
email_status: ["validated"]
fetch_count: 5000
Example 2 — UK CTOs
contact_job_title: ["CTO","Head of Engineering","VP Engineering"]
contact_location: ["united kingdom"]
email_status: ["validated","unknown"]
Example 3 — Amsterdam city-only (no broader Location)
contact_city: ["amsterdam"]
contact_location: (leave empty)
✅ Best practices
Location vs City: Choose one. Use Location for region/country/state or leave it empty and use City for city-only targeting. Same rule for Exclude.
Start broad, then narrow. Begin with Location + title, then add industry/revenue/funding.
Use include & exclude. Quickly remove irrelevant sectors with company_not_industry / company_not_keywords.
Prefer validated emails. Keep email_status = ["validated"] for outreach-ready lists; add unknown to increase volume.
Deduplicate downstream. If you merge runs, dedupe by email → linkedin → (full_name,company_domain).
Stay compliant. Use for B2B prospecting; follow GDPR/CCPA/PECR and local rules.
🧪 Output view (in the Apify UI)
The Overview tab shows a sortable table with links for company_website, linkedin, and company_linkedin. Export any time to CSV/JSON/XLSX from the Dataset.

🧰 API usage
Run via API with the same input JSON as the UI.

POST a run with your input JSON.
Poll for completion.
Fetch dataset items (JSON/CSV).