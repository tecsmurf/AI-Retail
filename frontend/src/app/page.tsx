import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight, BadgeCheck, Cctv, Clock, EyeOff, FileLock2, LayoutDashboard, MapPinned, Route,
  ScanLine, ShoppingBasket, Timer, Trash2, Users,
} from "lucide-react";
import { Wordmark } from "@/components/brand";
import { NavActions } from "@/components/landing/nav-actions";
import { StoreFloor } from "@/components/landing/store-floor";

export const metadata: Metadata = {
  title: { absolute: "Footrail: store analytics from the CCTV you already have" },
};

/** Set NEXT_PUBLIC_CONTACT_EMAIL to show "Request a pilot" mail buttons. */
const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() || null;
const PILOT_MAILTO = CONTACT_EMAIL
  ? `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("Footrail store pilot")}`
  : null;

const QUESTIONS = [
  {
    icon: Users,
    q: "How many people walked in today, and how many of them bought?",
    measure: "Entries and exits at the door, matched with bills from your POS export.",
    decision: "See true conversion per store and per hour, not just sales.",
  },
  {
    icon: Timer,
    q: "When do I need one more billing counter open?",
    measure: "Wait time in the billing queue and people who leave the line.",
    decision: "Staff counters to the hours that actually back up.",
  },
  {
    icon: MapPinned,
    q: "Is the new promo display getting noticed?",
    measure: "Visits and dwell time in each zone you draw on the camera view.",
    decision: "Keep, move or drop a display based on how shoppers react.",
  },
  {
    icon: Route,
    q: "Where do shoppers go after they come in?",
    measure: "The common paths between zones within a camera's view.",
    decision: "Place high-margin products on the routes people already walk.",
  },
  {
    icon: Clock,
    q: "Which hours am I over- or under-staffed?",
    measure: "Entries hour by hour in the store's own time zone.",
    decision: "Match floor and billing rosters to real footfall.",
  },
];

const STEPS = [
  {
    icon: Cctv,
    title: "Use the cameras you have",
    body: "An entrance camera and a billing camera are enough to start. Footrail works from recordings exported from your NVR, so nothing new goes on the shop floor.",
  },
  {
    icon: ScanLine,
    title: "AI counts people, not faces",
    body: "A person detector (YOLO11) finds people in each frame and a tracker (ByteTrack) follows each one as an anonymous box with a number.",
  },
  {
    icon: ShoppingBasket,
    title: "Boxes become store events",
    body: "Crossing the entry line, standing in a zone, waiting in the billing queue. Only these events and counts are kept for analysis.",
  },
  {
    icon: LayoutDashboard,
    title: "Answers on a dashboard",
    body: "Footfall, conversion, dwell and queues per store, on a laptop or a phone, with every number labelled with the footage behind it.",
  },
];

const PRIVACY = [
  { icon: EyeOff, title: "No facial recognition", body: "Footrail never identifies who someone is. People are anonymous boxes with a temporary number." },
  { icon: Trash2, title: "Footage is not kept", body: "Uploaded video is deleted after 30 days by default. The analytics keep only counts, times and zones." },
  { icon: FileLock2, title: "Ready for DPDP review", body: "We provide draft in-store signage, a privacy notice and a data map for your legal team." },
];

export default function LandingPage() {
  return (
    <div className="lp">
      {/* Nav */}
      <header className="lp-nav">
        <div className="lp-wrap flex h-16 items-center justify-between gap-4">
          <Link href="/" aria-label="Footrail home"><Wordmark /></Link>
          <nav className="hidden items-center gap-7 text-sm text-[var(--lp-ink-2)] md:flex">
            <a href="#questions" className="hover:text-[var(--lp-ink)]">What you learn</a>
            <a href="#how" className="hover:text-[var(--lp-ink)]">How it works</a>
            <a href="#privacy" className="hover:text-[var(--lp-ink)]">Privacy</a>
            <a href="#pilot" className="hover:text-[var(--lp-ink)]">Pilot</a>
          </nav>
          <NavActions />
        </div>
      </header>

      {/* Hero */}
      <section className="lp-wrap grid items-center gap-10 pb-16 pt-10 sm:pt-16 lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:pb-24">
        <div>
          <p className="lp-eyebrow">Retail analytics from existing CCTV</p>
          <h1 className="lp-h1 mt-4">
            Your cameras already see every shopper. <span className="text-[var(--lp-violet)]">Footrail tells you what they did.</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-[var(--lp-ink-2)]">
            Your billing system records everyone who bought. Nobody records the people who walked in, looked around and left.
            Footrail counts them from the CCTV you already own, so every store knows its footfall, conversion, busy zones and billing queues.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href={PILOT_MAILTO ?? "#pilot"} className="lp-btn lp-btn-primary lp-btn-lg">
              {PILOT_MAILTO ? "Request a store pilot" : "See the pilot offer"} <ArrowRight className="h-4 w-4" />
            </a>
            <a href="#demo" className="lp-btn lp-btn-ghost lp-btn-lg">Watch the 80-second demo</a>
          </div>
          <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-[var(--lp-ink-2)]">
            <li className="flex items-center gap-2"><BadgeCheck className="h-4 w-4 text-[var(--lp-mint-ink)]" /> No facial recognition</li>
            <li className="flex items-center gap-2"><BadgeCheck className="h-4 w-4 text-[var(--lp-mint-ink)]" /> No new cameras</li>
            <li className="flex items-center gap-2"><BadgeCheck className="h-4 w-4 text-[var(--lp-mint-ink)]" /> Built for multi-store chains</li>
          </ul>
        </div>

        <div className="lp-panel">
          <div className="flex items-center justify-between px-4 pb-2 pt-3 text-[11px] font-medium uppercase tracking-[0.08em] text-[#a49dbd]">
            <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#ff5d73]" /> Store floor, top view</span>
            <span>Illustration</span>
          </div>
          <StoreFloor />
          <div className="grid grid-cols-3 border-t border-white/10 text-white">
            <HeroStat label="Walked in" sub="counted at the door" />
            <HeroStat label="Where they went" sub="zone visits and dwell" />
            <HeroStat label="Waited at billing" sub="queue time" />
          </div>
        </div>
      </section>

      {/* The gap */}
      <section className="border-y border-[var(--lp-line)] bg-[var(--lp-card)]">
        <div className="lp-wrap grid gap-10 py-16 lg:grid-cols-[1fr_1.2fr] lg:py-20">
          <div>
            <p className="lp-eyebrow">The blind spot</p>
            <h2 className="lp-h2 mt-3">Sales tell you what happened at the counter. Not on the floor.</h2>
            <p className="mt-4 leading-relaxed text-[var(--lp-ink-2)]">
              A store can have a record sales day and still lose shoppers to a long billing line or a hidden aisle.
              Without footfall, there is no way to tell a busy day with poor conversion from a quiet day that converted well.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-[var(--lp-line)] p-6">
              <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-[var(--lp-muted)]">What stores know today</h3>
              <ul className="lp-list mt-4">
                <li>Bills, items and revenue</li>
                <li>Stock on shelves</li>
                <li>Staff rosters</li>
              </ul>
            </div>
            <div className="rounded-2xl border-2 border-[var(--lp-violet)] bg-[var(--lp-violet-soft)] p-6">
              <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-[var(--lp-violet)]">What Footrail adds</h3>
              <ul className="lp-list lp-list-on mt-4">
                <li>How many people came in, by hour</li>
                <li>Conversion: bills ÷ entries</li>
                <li>Which zones pull people in, and for how long</li>
                <li>How long the billing queue really is</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Questions -> decisions */}
      <section id="questions" className="lp-wrap scroll-mt-20 py-16 lg:py-24">
        <p className="lp-eyebrow">What you learn</p>
        <h2 className="lp-h2 mt-3 max-w-2xl">Questions every store manager asks, answered with numbers.</h2>
        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {QUESTIONS.map(({ icon: Icon, q, measure, decision }) => (
            <article key={q} className="lp-card flex flex-col">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--lp-violet-soft)] text-[var(--lp-violet)]">
                <Icon className="h-5 w-5" />
              </span>
              <h3 className="mt-4 text-lg font-semibold leading-snug tracking-tight">{q}</h3>
              <dl className="mt-4 space-y-3 text-sm leading-relaxed">
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--lp-muted)]">Footrail measures</dt>
                  <dd className="mt-1 text-[var(--lp-ink-2)]">{measure}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--lp-mint-ink)]">So you can</dt>
                  <dd className="mt-1 font-medium">{decision}</dd>
                </div>
              </dl>
            </article>
          ))}
          <article className="lp-card flex flex-col justify-between bg-[var(--lp-ink)] text-white">
            <div>
              <h3 className="text-lg font-semibold leading-snug tracking-tight">Every number shows its source.</h3>
              <p className="mt-3 text-sm leading-relaxed text-white/70">
                The dashboard says how many hours of footage sit behind each figure, which cameras they came from,
                and when a metric can&apos;t be measured yet. No guessed numbers.
              </p>
            </div>
            <Link href="/overview" className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-[#5ef0b4]">
              Open the dashboard <ArrowRight className="h-4 w-4" />
            </Link>
          </article>
        </div>
      </section>

      {/* Demo video */}
      <section id="demo" className="scroll-mt-16 bg-[var(--lp-dark)] text-white">
        <div className="lp-wrap grid items-center gap-10 py-16 lg:grid-cols-[1fr_1.6fr] lg:py-20">
          <div>
            <p className="lp-eyebrow text-[#5ef0b4]">See it work</p>
            <h2 className="lp-h2 mt-3 text-white">From a CCTV frame to a store dashboard in 80 seconds.</h2>
            <ol className="mt-6 space-y-3 text-sm text-white/75">
              {["A camera view of the sales floor", "People found as anonymous boxes", "Zones, dwell time and the billing queue", "The numbers a store manager sees"].map((t, i) => (
                <li key={t} className="flex gap-3">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-white/10 text-xs font-semibold">{i + 1}</span>
                  {t}
                </li>
              ))}
            </ol>
            <p className="mt-6 text-xs text-white/50">The video uses sample footage and sample numbers, marked on screen.</p>
          </div>
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-black shadow-2xl">
            <video
              className="aspect-video w-full"
              controls
              preload="none"
              playsInline
              poster="/media/how-it-works-poster.jpg"
            >
              <source src="/media/footrail-how-it-works.mp4" type="video/mp4" />
            </video>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="lp-wrap scroll-mt-20 py-16 lg:py-24">
        <p className="lp-eyebrow">How it works</p>
        <h2 className="lp-h2 mt-3 max-w-2xl">Four steps from the camera on your ceiling to a decision.</h2>
        <ol className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ icon: Icon, title, body }, i) => (
            <li key={title} className="lp-card relative">
              <div className="flex items-center justify-between">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--lp-ink)] text-white"><Icon className="h-5 w-5" /></span>
                <span className="text-3xl font-semibold tabular-nums text-[var(--lp-line-strong)]">0{i + 1}</span>
              </div>
              <h3 className="mt-5 font-semibold tracking-tight">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--lp-ink-2)]">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Privacy */}
      <section id="privacy" className="scroll-mt-16 border-y border-[var(--lp-line)] bg-[var(--lp-card)]">
        <div className="lp-wrap grid gap-10 py-16 lg:grid-cols-[1fr_1.6fr] lg:py-20">
          <div>
            <p className="lp-eyebrow">Privacy by design</p>
            <h2 className="lp-h2 mt-3">We count shoppers. We never know who they are.</h2>
            <p className="mt-4 leading-relaxed text-[var(--lp-ink-2)]">
              Footrail is built so that a store can use it without collecting personal data about shoppers.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {PRIVACY.map(({ icon: Icon, title, body }) => (
              <div key={title} className="rounded-2xl border border-[var(--lp-line)] p-6">
                <Icon className="h-6 w-6 text-[var(--lp-violet)]" />
                <h3 className="mt-4 font-semibold tracking-tight">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--lp-ink-2)]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Proof, stated honestly */}
      <section className="lp-wrap py-16 lg:py-24">
        <div className="grid gap-10 lg:grid-cols-[1fr_1.4fr]">
          <div>
            <p className="lp-eyebrow">Where we are</p>
            <h2 className="lp-h2 mt-3">Measured so far, and what your pilot will check.</h2>
            <p className="mt-4 leading-relaxed text-[var(--lp-ink-2)]">
              We publish what we have tested and what we haven&apos;t. Accuracy depends on camera angle and lighting,
              so every pilot starts by checking Footrail&apos;s counts against a hand count in your own store.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <ProofStat value="55 of 58" label="people detected in public test footage, with zero false detections" />
            <ProofStat value="~17 min" label="to analyse one hour of video on a 4-core server" />
            <ProofStat value="Week 1" label="of a pilot: Footrail counts compared with a hand count at your door" accent />
            <p className="text-xs leading-relaxed text-[var(--lp-muted)] sm:col-span-3">
              Test footage: three public sample clips (36 frames). People only partly in view are the most common miss.
              Results in your store will differ and are measured during the pilot before anyone relies on them.
            </p>
          </div>
        </div>
      </section>

      {/* Pilot */}
      <section id="pilot" className="lp-wrap scroll-mt-20 pb-20">
        <div className="overflow-hidden rounded-3xl bg-[var(--lp-violet)] text-white">
          <div className="grid gap-10 p-8 sm:p-12 lg:grid-cols-[1.2fr_1fr]">
            <div>
              <p className="lp-eyebrow text-white/70">Start with one store</p>
              <h2 className="lp-h2 mt-3 text-white">A paid pilot that proves the numbers before you roll out.</h2>
              <p className="mt-4 max-w-xl leading-relaxed text-white/80">
                We set Footrail up on one store&apos;s existing cameras, check its counts against your own,
                and hand over the dashboard and a report your regional team can act on.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                {PILOT_MAILTO ? (
                  <a href={PILOT_MAILTO} className="lp-btn lp-btn-lg bg-white text-[var(--lp-violet)] hover:bg-white/90">
                    Request a pilot <ArrowRight className="h-4 w-4" />
                  </a>
                ) : null}
                <Link href="/login" className="lp-btn lp-btn-lg border border-white/40 text-white hover:bg-white/10">
                  Sign in to your stores
                </Link>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
              <div className="rounded-2xl bg-white/10 p-5">
                <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-white/70">What we need from you</h3>
                <ul className="lp-list lp-list-light mt-3">
                  <li>Access to the entrance and billing cameras</li>
                  <li>A daily bill export from your POS (CSV)</li>
                  <li>A store contact for a one-day setup</li>
                </ul>
              </div>
              <div className="rounded-2xl bg-white/10 p-5">
                <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-white/70">What you get</h3>
                <ul className="lp-list lp-list-light mt-3">
                  <li>Daily footfall, conversion, zones and queues</li>
                  <li>An accuracy check against a hand count</li>
                  <li>A findings report for the store and region</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-[var(--lp-line)]">
        <div className="lp-wrap flex flex-col gap-3 py-8 text-sm text-[var(--lp-muted)] sm:flex-row sm:items-center sm:justify-between">
          <Wordmark markClassName="h-6 w-6" className="text-[var(--lp-ink)]" />
          <p>Anonymous retail analytics from existing CCTV. No facial recognition.</p>
        </div>
      </footer>
    </div>
  );
}

function HeroStat({ label, sub }: { label: string; sub: string }) {
  return (
    <div className="border-r border-white/10 px-4 py-3 last:border-r-0">
      <div className="text-sm font-semibold leading-tight">{label}</div>
      <div className="mt-0.5 text-[11px] leading-tight text-white/55">{sub}</div>
    </div>
  );
}

function ProofStat({ value, label, accent }: { value: string; label: string; accent?: boolean }) {
  return (
    <div className={accent ? "rounded-2xl bg-[var(--lp-ink)] p-6 text-white" : "rounded-2xl border border-[var(--lp-line)] bg-[var(--lp-card)] p-6"}>
      <div className={accent ? "text-3xl font-semibold tracking-tight text-[#5ef0b4]" : "text-3xl font-semibold tracking-tight"}>{value}</div>
      <p className={accent ? "mt-2 text-sm leading-relaxed text-white/70" : "mt-2 text-sm leading-relaxed text-[var(--lp-ink-2)]"}>{label}</p>
    </div>
  );
}
