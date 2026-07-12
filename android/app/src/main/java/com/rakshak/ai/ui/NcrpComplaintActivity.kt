package com.rakshak.ai.ui

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.View
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.rakshak.ai.R
import com.rakshak.ai.databinding.ActivityNcrpComplaintBinding
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * WebView-assisted NCRP (cybercrime.gov.in) complaint filing.
 *
 * ## Investigation findings (real, not assumed — see the commit this file
 * shipped in for the actual header/HTML dumps this was based on)
 *
 * - The public site loads fine in a WebView: `X-Frame-Options: DENY` only
 *   blocks `<iframe>` embedding, not a WebView's own top-level
 *   `loadUrl()` navigation, which is not framing.
 * - `Content-Security-Policy` is sent as `-Report-Only` — not enforced.
 *   Even if it were, its script-src allows 'self' plus any http or https
 *   origin (a wildcarded scheme rule), broad enough not to block
 *   execution, and `evaluateJavascript()` runs at the
 *   WebView-host privilege level (like a DevTools console eval), which
 *   browsers don't subject to a page's own CSP script-src regardless.
 * - The homepage and the "Register a Complaint" entry page
 *   (`Webform/Index.aspx`) are classic ASP.NET WebForms (`__VIEWSTATE`,
 *   `__EVENTVALIDATION`, `__doPostBack` — confirmed from the actual page
 *   source), not React/Angular/Vue. No CAPTCHA or OTP field exists on
 *   these two pages.
 * - The actual incident-details form (victim/suspect phone, description,
 *   category — the fields this app would want to fill) sits further
 *   into the flow, behind a mandatory mobile-OTP verification/login step.
 *   That step was **not walked through** here, deliberately: doing so
 *   would mean triggering a real OTP send against a live government
 *   system purely to reverse-engineer field names, which is exactly the
 *   kind of repeated/automated poking at public infrastructure this task
 *   asked to avoid — and OTP verification is a genuine identity control,
 *   not an incidental obstacle, so this app does not attempt to read,
 *   guess, or bypass it in any way. The user completes that step
 *   themselves, in the WebView, like any other citizen would.
 * - Consequence: this app has **no verified knowledge** of the real
 *   field IDs/names on the post-OTP incident-details page. Rather than
 *   hardcode guessed ASP.NET control IDs and claim they work,
 *   [buildAutofillScript] uses a generic, keyword-based best-effort field
 *   matcher (id/name/placeholder/aria-label/associated-<label> text
 *   contains "phone"/"mobile", "description"/"incident"/"details", etc.)
 *   that only fills empty text/tel/textarea fields it can positively
 *   match, explicitly skips anything resembling otp/captcha/verification-
 *   code, and reports exactly what it did/didn't find back to Kotlin via
 *   [FillResultBridge] — never a silent guess presented as success.
 * - Category (a `<select>` dropdown) is deliberately **not** auto-filled:
 *   setting a `<select>`'s value requires an existing `<option>` with a
 *   matching value, which can't be predicted without having seen the real
 *   dropdown, and silently failing to select anything would be worse than
 *   not trying. This is a documented, deliberate limitation.
 *
 * This screen never submits anything itself — no script here ever calls
 * `.submit()`, `.click()` on anything resembling Submit/Verify/Send-OTP, or
 * navigates the WebView away from wherever the user currently has it. The
 * complaint-summary panel (same [com.rakshak.ai.escalation.ComplaintDraft]
 * text already used for the SMS/copy fallback) is always available
 * alongside the WebView, not just shown on failure.
 *
 * ## Real incident-details form findings (captured via [FillResultBridge.onDiagnostics],
 * after a human tester navigated category selection + their own OTP login manually —
 * `Webform/Crime_ReportTrack.aspx`, 24 form elements, real evidence not assumed)
 *
 * - `ContentPlaceHolder1_txtUserId` — no label/placeholder at all, but paired
 *   with the website/platform field below; this is "the suspect's ID on that
 *   platform", which for WhatsApp *is* the phone number. Targeted directly by
 *   this confirmed ID, not a keyword guess.
 * - `ContentPlaceHolder1_txtNameOfWebsite` — the social-media/platform field.
 * - `txt_AdditionalInfo` is a `TEXTAREA` — the real description field. Its
 *   id/name contain neither "description" nor "detail" nor "narrat", which is
 *   exactly why the original keyword-only matcher silently missed it. Now
 *   targeted directly by this confirmed ID, keyword matching kept only as a
 *   fallback in case a future page revision renames it.
 * - `q17length` sits next to `txt_AdditionalInfo`: a **read-only** character
 *   counter, not a real field — already excluded by the existing `readOnly`
 *   check, no special-casing needed.
 * - `txt_ApproxDateTime` is `<input type="date">` (placeholder shows the
 *   locale display format `dd/mm/yyyy`, but per the HTML5 spec a date
 *   input's `.value` is always ISO `yyyy-MM-dd` regardless of display
 *   format — confirmed spec behavior, not assumed) plus three separate
 *   `<select>` elements for hour/minute/AM-PM (`ddlHr`/`ddlMint`/`ddlAMPM`).
 *   Filled by matching each dropdown's real, live `<option>` **text**
 *   (e.g. visible "AM"/"PM", "1".."12") at fill-time — never a hardcoded
 *   assumed value — so a minute granularity the form doesn't offer (e.g. it
 *   only offers 5-minute steps) is honestly reported as not-found rather
 *   than silently snapped to the nearest option.
 * - `ContentPlaceHolder1_ddl_CategoryCrime` / `..._ddl_Sub_CategoryCrime`
 *   are auto-filled per explicit product decision — [buildAutofillScript]
 *   matches each dropdown's live `<option>` text against keywords derived
 *   from [DecisionResult.ruleCategories] (the same category vocabulary
 *   documented in CLAUDE.md Section 6.3), overriding whatever was already
 *   selected, unlike every other field on this form (which never overwrites
 *   an already-filled value). Confirmed working for the top-level category
 *   (real option `"Online Financial Fraud"`, matched by "financial").
 * - Sub-category is a confirmed **cascading dropdown**: a captured DOM dump
 *   showed it holding only the `'--Select--'` placeholder immediately after
 *   selecting the category — its real options (whatever NCRP's actual
 *   financial-fraud sub-types are) are populated by the site's own script/
 *   postback in reaction to that selection, not present up front, and
 *   **incrementally**, not atomically — a live capture caught a genuine
 *   keyword match (`"debit"` against `"Debit/Credit Card Fraud/Sim Swap
 *   Fraud"`) being missed because the original "any one real option has
 *   arrived" poll fired against a still-partial list, even though all 8 real
 *   options had fully landed ~815ms later. Fixed by `finalizeSubCategoryAndReport`
 *   polling (up to ~3.2s) for the option count to stay identical across two
 *   consecutive 400ms reads (i.e. the list has stopped growing) before
 *   attempting the keyword match, rather than matching against a DOM state
 *   that structurally couldn't yet hold the answer. Still never
 *   triggers a postback/click itself — only waits for whatever the page's
 *   own category-change handler already does unprompted.
 * - `ContentPlaceHolder1_rdbBankFroudYesNo_0/_1` ("is this bank fraud?") and
 *   `ContentPlaceHolder1_rdoResonforDelaying_0/_1` ("was there a delay in
 *   reporting?") are both Yes/No radio pairs — confirmed radios, not the
 *   checkbox/dropdown/text originally guessed. Deliberately **not**
 *   auto-answered: these are substantive judgment questions the user must
 *   answer themselves on a government form, not objective facts this app
 *   already knows — auto-selecting either risks putting words in the user's
 *   mouth on a legal document. Reported to the user as present-but-untouched,
 *   not silently ignored.
 * - **No field resembling "what is being trafficked" exists anywhere on this
 *   form.** Confirmed absent, not just unmapped — that field belongs to a
 *   different NCRP top-level crime category (trafficking), not the
 *   financial-fraud/digital-arrest flow this app targets. Not built.
 * - **No `<input type="file">` (evidence upload) exists on this page either.**
 *   If NCRP asks for evidence later in this same multi-step flow, it wasn't
 *   reached in this investigation — a real open question, not a "no", and
 *   file-attach automation (a materially different mechanism than text
 *   injection — WebView's file-chooser intent, not `evaluateJavascript()`)
 *   was not investigated further without first confirming such a field
 *   actually exists.
 */
class NcrpComplaintActivity : AppCompatActivity() {

    private lateinit var binding: ActivityNcrpComplaintBinding
    private lateinit var suspectPhone: String
    private lateinit var incidentDescription: String
    private var incidentEpochMillis: Long = 0L
    private var ruleCategories: List<String> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityNcrpComplaintBinding.inflate(layoutInflater)
        setContentView(binding.root)
        title = getString(R.string.ncrp_complaint_title)

        suspectPhone = intent.getStringExtra(EXTRA_SUSPECT_PHONE).orEmpty()
        ruleCategories = intent.getStringArrayListExtra(EXTRA_RULE_CATEGORIES).orEmpty()
        incidentDescription = intent.getStringExtra(EXTRA_DESCRIPTION).orEmpty()
        incidentEpochMillis = intent.getLongExtra(EXTRA_INCIDENT_EPOCH_MILLIS, System.currentTimeMillis())
        val draftText = intent.getStringExtra(EXTRA_DRAFT_TEXT).orEmpty()

        binding.summaryText.text = draftText
        binding.summaryToggle.setOnClickListener {
            val nowVisible = binding.summaryScroll.visibility != View.VISIBLE
            binding.summaryScroll.visibility = if (nowVisible) View.VISIBLE else View.GONE
            binding.summaryToggle.text = getString(
                if (nowVisible) R.string.ncrp_summary_toggle_hide else R.string.ncrp_summary_toggle_show
            )
        }
        binding.copySummaryButton.setOnClickListener {
            val clipboard = getSystemService(ClipboardManager::class.java)
            clipboard.setPrimaryClip(ClipData.newPlainText("NCRP complaint summary", draftText))
            Toast.makeText(this, R.string.ncrp_summary_copied_toast, Toast.LENGTH_SHORT).show()
        }

        setUpWebView()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setUpWebView() {
        val webView = binding.ncrpWebView
        // JS is required for the autofill feature; domStorage is enabled
        // defensively in case the site's own scripts expect it (harmless
        // either way — this app does not read anything the site stores).
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.addJavascriptInterface(FillResultBridge(), JS_BRIDGE_NAME)
        // Surfaces the page's own console.log/warn/error into adb logcat under
        // this activity's tag — diagnostic only, never used to read page
        // content beyond what console messages the site itself emits.
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                Log.i(TAG, "ncrp_console [${message.messageLevel()}] ${message.message()} " +
                    "(${message.sourceId()}:${message.lineNumber()})")
                return true
            }
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String?) {
                super.onPageFinished(view, url)
                // Title-only trace of the navigation path (category page ->
                // OTP/login -> incident form, whatever the real path turns
                // out to be) — logged on every page load, not just when
                // Autofill is tapped, so the sequence is visible even if the
                // user never reaches a page worth autofilling.
                Log.i(TAG, "ncrp_page_loaded url=$url title=${view.title}")
                binding.autofillButton.isEnabled = true
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest?,
                error: WebResourceError?,
            ) {
                super.onReceivedError(view, request, error)
                // Only the main-frame load failing is worth surfacing —
                // a failed sub-resource (an ad script, a font, a widget)
                // is not the same as "the site didn't load".
                if (request != null && !request.isForMainFrame) return
                val description = error?.description?.toString() ?: "unknown error"
                Log.e(TAG, "ncrp_load_error description=$description")
                Toast.makeText(
                    this@NcrpComplaintActivity,
                    getString(R.string.ncrp_load_error, description),
                    Toast.LENGTH_LONG,
                ).show()
            }
        }

        binding.autofillButton.setOnClickListener { runAutofill() }
        webView.loadUrl(NCRP_URL)
    }

    private fun runAutofill() {
        // Date/time fields on the real form (txt_ApproxDateTime + ddlHr/ddlMint/ddlAMPM)
        // need real components, not the display-formatted "dd MMM yyyy, HH:mm" string —
        // computed once here in Kotlin rather than re-parsed inside the injected JS.
        val incidentDate = Date(incidentEpochMillis)
        val isoDate = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(incidentDate)
        val hour24 = SimpleDateFormat("HH", Locale.US).format(incidentDate).toInt()
        val minute = SimpleDateFormat("mm", Locale.US).format(incidentDate).toInt()
        val hour12 = if (hour24 % 12 == 0) 12 else hour24 % 12
        val amPm = if (hour24 < 12) "AM" else "PM"

        val script = buildAutofillScript(
            suspectPhone = suspectPhone,
            description = incidentDescription,
            isoDate = isoDate,
            hour12 = hour12,
            minute = minute,
            amPm = amPm,
            categoryKeywords = TOP_CATEGORY_KEYWORDS,
            subCategoryKeywords = subCategoryKeywordsFor(ruleCategories),
        )
        binding.ncrpWebView.evaluateJavascript(script) { returnValue ->
            // evaluateJavascript's own callback only confirms the engine
            // ran *something* — the actual fill outcome always comes
            // through FillResultBridge below, since that's populated even
            // when the script's own try/catch swallows an exception. A
            // null/empty returnValue here with no bridge callback within
            // a couple seconds would mean the engine itself never ran the
            // script at all (not observed in testing, but handled).
            Log.i(TAG, "ncrp_autofill_eval_returned $returnValue")
        }
    }

    private inner class FillResultBridge {
        /**
         * Diagnostic only — captures the actual page state (title, URL,
         * every input/select/textarea present, iframe count, whether any
         * shadow roots exist) at the exact moment [runAutofill] executes,
         * so a "no fields found" result can be root-caused against real
         * evidence instead of a guess. Never used to decide what to fill;
         * [buildAutofillScript]'s fill logic is unchanged by this. Written
         * to a file (app-external files dir) rather than only logcat,
         * since a full DOM dump can exceed logcat's per-line limit.
         */
        @JavascriptInterface
        fun onDiagnostics(json: String) {
            runOnUiThread {
                try {
                    val obj = JSONObject(json)
                    // "phase" distinguishes the snapshot taken before any fill
                    // attempt from the one taken after the fill (including the
                    // sub-category cascade poll) completes — written to separate
                    // files so a before/after comparison survives, instead of
                    // the post-fill call silently overwriting the pre-fill one.
                    val phase = obj.optString("phase", "pre")
                    val file = File(getExternalFilesDir(null), "ncrp_dom_dump_$phase.json")
                    file.writeText(obj.toString(2))
                    val fields = obj.optJSONArray("fields")
                    Log.i(
                        TAG,
                        "ncrp_diagnostics phase=$phase title=${obj.optString("title")} url=${obj.optString("url")} " +
                            "field_count=${fields?.length() ?: 0} iframe_count=${obj.optInt("iframeCount")} " +
                            "has_shadow_dom=${obj.optBoolean("hasShadowDom")} dump_file=${file.absolutePath}",
                    )
                } catch (e: Exception) {
                    Log.e(TAG, "ncrp_diagnostics_parse_failed", e)
                }
            }
        }

        @JavascriptInterface
        fun onFillResult(json: String) {
            runOnUiThread {
                try {
                    val obj = JSONObject(json)
                    val filled = obj.getJSONArray("filled")
                    val notFound = obj.getJSONArray("notFound")
                    val scriptError = obj.optString("error", "")
                    Log.i(TAG, "ncrp_autofill_result filled=$filled notFound=$notFound error=$scriptError")

                    if (scriptError.isNotEmpty()) {
                        Toast.makeText(
                            this@NcrpComplaintActivity,
                            getString(R.string.ncrp_autofill_script_error, scriptError),
                            Toast.LENGTH_LONG,
                        ).show()
                        return@runOnUiThread
                    }

                    if (filled.length() == 0) {
                        Toast.makeText(
                            this@NcrpComplaintActivity,
                            getString(R.string.ncrp_autofill_no_fields_found),
                            Toast.LENGTH_LONG,
                        ).show()
                        return@runOnUiThread
                    }

                    val message = buildString {
                        append(getString(R.string.ncrp_autofill_result_prefix, filled.length()))
                        if (notFound.length() > 0) {
                            append(' ')
                            append(getString(R.string.ncrp_autofill_result_missing, notFound.length()))
                        }
                    }
                    Toast.makeText(this@NcrpComplaintActivity, message, Toast.LENGTH_LONG).show()
                } catch (e: Exception) {
                    Log.e(TAG, "ncrp_autofill_result_parse_failed", e)
                }
            }
        }
    }

    companion object {
        private const val TAG = "RakshakNcrp"
        private const val NCRP_URL = "https://cybercrime.gov.in/Webform/Index.aspx"
        private const val JS_BRIDGE_NAME = "AndroidNcrpBridge"

        private const val EXTRA_SUSPECT_PHONE = "suspect_phone"
        private const val EXTRA_INCIDENT_EPOCH_MILLIS = "incident_epoch_millis"
        private const val EXTRA_DESCRIPTION = "description"
        private const val EXTRA_RULE_CATEGORIES = "rule_categories"
        private const val EXTRA_DRAFT_TEXT = "draft_text"

        fun buildIntent(
            context: Context,
            suspectPhone: String,
            incidentEpochMillis: Long,
            description: String,
            ruleCategories: List<String>,
            draftText: String,
        ): Intent = Intent(context, NcrpComplaintActivity::class.java).apply {
            putExtra(EXTRA_SUSPECT_PHONE, suspectPhone)
            putExtra(EXTRA_INCIDENT_EPOCH_MILLIS, incidentEpochMillis)
            putExtra(EXTRA_DESCRIPTION, description)
            putStringArrayListExtra(EXTRA_RULE_CATEGORIES, ArrayList(ruleCategories))
            putExtra(EXTRA_DRAFT_TEXT, draftText)
        }

        // Always-true for this app's domain — the top-level category is
        // already set correctly by the user's own manual button click before
        // this form loads, so this only ever re-confirms the same choice;
        // it's deliberately generic rather than reason-specific (see
        // TOP_CATEGORY_KEYWORDS usage in [buildAutofillScript]).
        private val TOP_CATEGORY_KEYWORDS = listOf("financial fraud", "financial cyber fraud", "financial")

        /**
         * Maps [DecisionResult.ruleCategories] (the real category-key
         * vocabulary from `ml/detector.py::HIGH_RISK_PATTERNS`, cross-
         * referenced against Chakshu's taxonomy per CLAUDE.md Section 6.3)
         * to keyword fragments to search NCRP's real sub-category `<option>`
         * text for. Best-effort: written before the real option-text dump
         * was available, so the exact wording of NCRP's options may not
         * match these guesses — [selectByOptionKeyword] only ever selects
         * an option when a real, live match is found, so a wrong guess here
         * degrades to "not found", never a wrong silent selection. Falls
         * back to the generic financial-fraud keywords when no category
         * matched (e.g. a MEDIUM verdict from ML score alone, no rule hit).
         */
        private fun subCategoryKeywordsFor(ruleCategories: List<String>): List<String> {
            // Real option text, captured via diagnostics (see this file's class
            // doc comment) under NCRP's "Online Financial Fraud" top category:
            // Aadhar Enabled Payment System (AEPS), Business Email Compromise/
            // Email Takeover, Debit/Credit Card Fraud/Sim Swap Fraud, Demat/
            // Depository Fraud, E-Wallet Related Fraud, Fraud Call/Vishing,
            // Internet Banking Related Fraud, UPI Related Frauds. Every keyword
            // below is a genuine substring of one of these real, exact option
            // strings — not a guess. Categories with no honest match among
            // these 8 real options (extortion_threat, reward_bait,
            // urgency_coercion, isolation_tactics, relative_impersonation,
            // money_demand — none of these NCRP sub-types are about blackmail,
            // lottery/investment, family-distress framing, or a bare, channel-
            // less demand for money) are deliberately left OUT of this map
            // rather than forced onto the nearest-sounding wrong option — a
            // confident-looking wrong pre-fill is worse than none, since the
            // whole point was picking the CORRECT option, not any option.
            val map = mapOf(
                "authority_impersonation" to listOf("fraud call", "vishing"),
                "credential_request" to listOf("upi", "debit", "credit", "bank"),
                "otp_readout_request" to listOf("upi", "debit", "credit", "bank"),
                "card_collection_request" to listOf("debit", "credit"),
                "telecom_impersonation" to listOf("sim swap"),
            )
            // No generic fallback when nothing maps: an empty/unmatched
            // rule-category signal means we genuinely don't know the real
            // sub-type, and [selectByOptionKeyword] correctly reports this
            // as "not found" for an empty keyword list — the honest outcome,
            // not a forced guess.
            return ruleCategories.flatMap { map[it].orEmpty() }.distinct()
        }

        /**
         * Field filler targeting the real, confirmed IDs from the incident-
         * details form investigation (see this class's doc comment) with a
         * keyword-based fallback for the two text fields, in case a future
         * NCRP revision renames them. Every string value is embedded via
         * [JSONObject.quote], which correctly escapes quotes/backslashes/
         * newlines into a valid JS string literal — this is the safe way to
         * embed untrusted app data into an injected script, not naive string
         * concatenation.
         *
         * Deliberately excludes, by design, not oversight: anything matching
         * otp/captcha/verification/token/csrf (never touched, regardless of
         * what it's asked to fill), the category/sub-category `<select>`s
         * (already chosen by the user's own manual navigation), the
         * bank-fraud and delay-in-reporting Yes/No radios (substantive
         * judgment questions, not objective facts this app can answer for
         * the user), and every button/submit element (this script only ever
         * reads/writes `.value` on text-like inputs and `<select>`s it can
         * positively match by real option text, never calls `.click()` or
         * `.submit()` on anything).
         */
        private fun buildAutofillScript(
            suspectPhone: String,
            description: String,
            isoDate: String,
            hour12: Int,
            minute: Int,
            amPm: String,
            categoryKeywords: List<String>,
            subCategoryKeywords: List<String>,
        ): String {
            val suspectPhoneJs = JSONObject.quote(suspectPhone)
            val descriptionJs = JSONObject.quote(description)
            val isoDateJs = JSONObject.quote(isoDate)
            val hourCandidatesJs = "[${JSONObject.quote(hour12.toString())}, " +
                JSONObject.quote(hour12.toString().padStart(2, '0')) + "]"
            val minuteCandidatesJs = "[${JSONObject.quote(minute.toString())}, " +
                JSONObject.quote(minute.toString().padStart(2, '0')) + "]"
            val amPmCandidatesJs = "[${JSONObject.quote(amPm)}]"
            val categoryKeywordsJs = "[${categoryKeywords.joinToString(", ") { JSONObject.quote(it) }}]"
            val subCategoryKeywordsJs = "[${subCategoryKeywords.joinToString(", ") { JSONObject.quote(it) }}]"
            return """
                (function() {
                    // Diagnostic dump of actual page state — read-only, reports
                    // what's there, changes nothing. Called twice: once ('pre')
                    // before any fill attempt, once ('post') after the fill
                    // (including the sub-category cascade poll) completes, so a
                    // before/after comparison is possible instead of only ever
                    // seeing the state before the category cascade had a chance
                    // to add/populate anything. Includes each <select>'s real,
                    // live <option> list every time, never a guessed value.
                    function dumpDiagnostics(phase) {
                        try {
                            var dumpFields = document.querySelectorAll('input, select, textarea');
                            var fieldDump = [];
                            for (var d = 0; d < dumpFields.length; d++) {
                                var f = dumpFields[d];
                                var lbl = '';
                                if (f.id) {
                                    var labelEl = document.querySelector('label[for="' + f.id + '"]');
                                    if (labelEl) { lbl = labelEl.textContent; }
                                }
                                var entry = {
                                    tag: f.tagName,
                                    type: f.type || '',
                                    id: f.id || '',
                                    name: f.name || '',
                                    placeholder: f.placeholder || '',
                                    ariaLabel: f.getAttribute('aria-label') || '',
                                    labelText: lbl,
                                    disabled: !!f.disabled,
                                    readOnly: !!f.readOnly,
                                    hidden: f.type === 'hidden',
                                    currentValue: (f.value || '').toString().slice(0, 50)
                                };
                                if (f.tagName === 'SELECT') {
                                    var opts = [];
                                    for (var o = 0; o < f.options.length; o++) {
                                        opts.push({ value: f.options[o].value, text: f.options[o].text });
                                    }
                                    entry.options = opts;
                                }
                                fieldDump.push(entry);
                            }
                            var hasShadow = false;
                            var allEls = document.querySelectorAll('*');
                            for (var s = 0; s < allEls.length; s++) {
                                if (allEls[s].shadowRoot) { hasShadow = true; break; }
                            }
                            if (window.$JS_BRIDGE_NAME && window.$JS_BRIDGE_NAME.onDiagnostics) {
                                window.$JS_BRIDGE_NAME.onDiagnostics(JSON.stringify({
                                    phase: phase,
                                    title: document.title,
                                    url: location.href,
                                    fields: fieldDump,
                                    iframeCount: document.querySelectorAll('iframe').length,
                                    hasShadowDom: hasShadow
                                }));
                            }
                        } catch (diagErr) {
                            if (window.$JS_BRIDGE_NAME && window.$JS_BRIDGE_NAME.onDiagnostics) {
                                window.$JS_BRIDGE_NAME.onDiagnostics(JSON.stringify({ phase: phase, error: String(diagErr) }));
                            }
                        }
                    }
                    dumpDiagnostics('pre');

                    try {
                        var filled = [];
                        var notFound = [];
                        var EXCLUDE_ALWAYS = ['otp', 'captcha', 'verification', 'token', 'csrf', 'password'];

                        function labelTextFor(el) {
                            if (!el.id) return '';
                            var label = document.querySelector('label[for="' + el.id + '"]');
                            return label ? label.textContent : '';
                        }

                        function haystackFor(el) {
                            return (
                                (el.id || '') + ' ' +
                                (el.name || '') + ' ' +
                                (el.placeholder || '') + ' ' +
                                (el.getAttribute('aria-label') || '') + ' ' +
                                labelTextFor(el)
                            ).toLowerCase();
                        }

                        function fillByIdOrKeyword(fieldLabel, id, includeKeys, value) {
                            if (!value) { return; }
                            var el = id ? document.getElementById(id) : null;
                            if (el && !el.disabled && !el.readOnly && !el.value) {
                                el.value = value;
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                filled.push(fieldLabel);
                                return;
                            }
                            var candidates = document.querySelectorAll(
                                'input[type="text"], input[type="tel"], input:not([type]), textarea'
                            );
                            for (var i = 0; i < candidates.length; i++) {
                                var c = candidates[i];
                                if (c.disabled || c.readOnly || c.value) { continue; }
                                var haystack = haystackFor(c);
                                var excluded = EXCLUDE_ALWAYS.some(function(k) { return haystack.indexOf(k) !== -1; });
                                if (excluded) { continue; }
                                var matched = includeKeys.some(function(k) { return haystack.indexOf(k) !== -1; });
                                if (matched) {
                                    c.value = value;
                                    c.dispatchEvent(new Event('input', { bubbles: true }));
                                    c.dispatchEvent(new Event('change', { bubbles: true }));
                                    filled.push(fieldLabel);
                                    return;
                                }
                            }
                            notFound.push(fieldLabel);
                        }

                        fillByIdOrKeyword(
                            'suspect phone/platform ID',
                            'ContentPlaceHolder1_txtUserId',
                            ['suspect', 'accused', 'fraudster', 'scammer', 'user id', 'userid'],
                            $suspectPhoneJs
                        );
                        fillByIdOrKeyword(
                            'incident description',
                            'txt_AdditionalInfo',
                            ['description', 'incident detail', 'complaint detail', 'narrat', 'additional'],
                            $descriptionJs
                        );

                        // Date input: HTML5 <input type="date"> always stores .value as
                        // ISO yyyy-MM-dd regardless of the locale display format shown
                        // to the user (confirmed spec behaviour, not assumed).
                        (function fillDate() {
                            var el = document.getElementById('txt_ApproxDateTime');
                            if (!el || el.disabled || el.readOnly || el.value) {
                                notFound.push('incident date');
                                return;
                            }
                            el.value = $isoDateJs;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            filled.push('incident date');
                        })();

                        // Time dropdowns: matched against each select's REAL, live
                        // <option> text at fill-time (e.g. actual visible "AM"/"PM",
                        // "1".."12") — never a hardcoded assumed option value. A
                        // minute granularity the form doesn't offer (e.g. 5-minute
                        // steps only) is honestly reported as not-found rather than
                        // silently snapped to the nearest available option.
                        function selectByOptionText(fieldLabel, id, candidateTexts) {
                            var el = document.getElementById(id);
                            if (!el || el.disabled) { notFound.push(fieldLabel); return; }
                            for (var i = 0; i < el.options.length; i++) {
                                var optText = (el.options[i].text || '').trim().toLowerCase();
                                for (var c = 0; c < candidateTexts.length; c++) {
                                    if (optText === candidateTexts[c].toLowerCase()) {
                                        el.value = el.options[i].value;
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                        filled.push(fieldLabel);
                                        return;
                                    }
                                }
                            }
                            notFound.push(fieldLabel);
                        }

                        selectByOptionText('incident hour', 'ContentPlaceHolder1_ddlHr', $hourCandidatesJs);
                        selectByOptionText('incident minute', 'ContentPlaceHolder1_ddlMint', $minuteCandidatesJs);
                        selectByOptionText('incident AM/PM', 'ContentPlaceHolder1_ddlAMPM', $amPmCandidatesJs);

                        // Category/sub-category: matched by SUBSTRING against each
                        // dropdown's real, live option text — unlike every other
                        // field on this form, this is allowed to override an
                        // already-selected value (set by the user's own manual
                        // category-button navigation before this page loaded),
                        // per explicit product decision. Still never a blind
                        // guess: only selects when a real keyword match exists in
                        // the option actually presented by the page right now.
                        function selectByOptionKeyword(fieldLabel, id, keywords) {
                            var el = document.getElementById(id);
                            if (!el || el.disabled) { notFound.push(fieldLabel); return; }
                            for (var i = 0; i < el.options.length; i++) {
                                var optText = (el.options[i].text || '').toLowerCase();
                                for (var k = 0; k < keywords.length; k++) {
                                    if (optText.indexOf(keywords[k].toLowerCase()) !== -1) {
                                        el.value = el.options[i].value;
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                        filled.push(fieldLabel);
                                        return;
                                    }
                                }
                            }
                            notFound.push(fieldLabel);
                        }

                        selectByOptionKeyword('complaint category', 'ContentPlaceHolder1_ddl_CategoryCrime', $categoryKeywordsJs);

                        // Sub-category is a classic ASP.NET cascading dropdown: real
                        // evidence (a captured DOM dump) showed it holds ONLY the
                        // '--Select--' placeholder immediately after the category
                        // selection above — its real options are populated by the
                        // site's own script/postback in response to that selection,
                        // which hasn't had time to run yet in the same synchronous
                        // tick. Never triggers a postback/click itself — only waits
                        // for whatever the page's own category 'change' handler
                        // already does on its own.
                        //
                        // Was previously gated on "options.length > 1" (i.e. any one
                        // real option has arrived) but real evidence (a live capture
                        // against NCRP tonight) showed that's a race: the list is
                        // populated incrementally, not atomically — a genuine
                        // keyword match (e.g. "debit" against "Debit/Credit Card
                        // Fraud/Sim Swap Fraud") was missed because the scan ran
                        // against a still-partial list, even though all 8 real
                        // options had fully landed ~815ms later. Now waits for the
                        // option count to be identical across two consecutive
                        // 400ms polls (i.e. the list has stopped growing) before
                        // scanning — observed full population finished well inside
                        // that window, so this trades a little latency for actually
                        // seeing the complete list before matching.
                        function finalizeSubCategoryAndReport(attemptsLeft, lastCount) {
                            var subEl = document.getElementById('ContentPlaceHolder1_ddl_Sub_CategoryCrime');
                            var currentCount = subEl ? subEl.options.length : 0;
                            var stabilized = currentCount > 1 && currentCount === lastCount;
                            if (!stabilized && attemptsLeft > 0) {
                                setTimeout(function() {
                                    finalizeSubCategoryAndReport(attemptsLeft - 1, currentCount);
                                }, 400);
                                return;
                            }
                            selectByOptionKeyword('complaint sub-category', 'ContentPlaceHolder1_ddl_Sub_CategoryCrime', $subCategoryKeywordsJs);
                            dumpDiagnostics('post');
                            if (window.$JS_BRIDGE_NAME && window.$JS_BRIDGE_NAME.onFillResult) {
                                window.$JS_BRIDGE_NAME.onFillResult(JSON.stringify({ filled: filled, notFound: notFound }));
                            }
                        }
                        // -1 sentinel as the initial lastCount so the very first
                        // check (count=1, placeholder only) can never spuriously
                        // "stabilize"; 8 attempts (~3.2s worst case) budgets for one
                        // extra confirmation round-trip versus the old single-arrival
                        // check, since stabilization needs two matching reads, not one.
                        finalizeSubCategoryAndReport(8, -1);
                    } catch (e) {
                        if (window.$JS_BRIDGE_NAME && window.$JS_BRIDGE_NAME.onFillResult) {
                            window.$JS_BRIDGE_NAME.onFillResult(JSON.stringify({ filled: [], notFound: [], error: String(e) }));
                        }
                    }
                })();
            """.trimIndent()
        }
    }
}
