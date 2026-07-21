/**
 * Home page — universal, no exam-specific branding.
 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  Upload, FileText, BarChart3, CheckCircle,
  ChevronDown, ShieldCheck,
} from 'lucide-react';
import { PageLayout } from '@/components/layout/PageLayout';
import { UploadForm } from '@/features/upload/UploadForm';
import { useEvaluationStore } from '@/store/evaluationStore';

export function HomePage() {
  const { status } = useEvaluationStore();
  const navigate   = useNavigate();

  useEffect(() => {
    if (status === 'success') navigate('/results');
  }, [status, navigate]);

  return (
    <PageLayout>

      {/* ── HERO ─────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-hero-gradient">
        <div className="absolute inset-0 dot-grid" />
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(ellipse 70% 60% at 50% -10%, rgba(139,92,246,0.45) 0%, rgba(6,182,212,0.20) 55%, transparent 100%)',
          }}
        />

        <div className="container-pad relative py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">

            {/* Badge */}
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 py-1.5 text-sm text-white/80 backdrop-blur-sm">
              <ShieldCheck className="h-3.5 w-3.5 text-teal-400" />
              Any class · Any exam · Any subject
            </div>

            {/* Headline */}
            <h1 className="text-balance text-4xl font-black leading-[1.1] text-white sm:text-5xl lg:text-[3.5rem]">
              Check Any{' '}
              <span className="text-grad-hero">Answer Sheet</span>
              <br />
              Like a Real Teacher
            </h1>

            <p className="mx-auto mt-6 max-w-xl text-pretty text-base text-white/65 sm:text-lg">
              Upload a photo or PDF of a handwritten or typed answer — from
              Class 6 to college entrance. Get a full score sheet, red-ink
              annotations, and an improvement plan instantly.
            </p>

            {/* Feature pills */}
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              {FEATURE_PILLS.map(({ icon: Icon, label, colour }) => (
                <div
                  key={label}
                  className="flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm text-white/80 backdrop-blur-sm"
                >
                  <Icon className={clsx('h-3.5 w-3.5', colour)} />
                  {label}
                </div>
              ))}
            </div>

            <ChevronDown className="mx-auto mt-12 h-6 w-6 animate-bounce text-white/25" />
          </div>
        </div>
      </section>

      {/* ── UPLOAD CARD ──────────────────────────────────────────────── */}
      <section className="container-pad relative -mt-10 pb-16">
        <div className="mx-auto max-w-2xl">
          <div
            className="rounded-3xl border border-slate-100 bg-white p-6 sm:p-8"
            style={{ boxShadow: '0 24px 80px rgba(0,0,0,0.14)' }}
          >
            <div className="mb-6 text-center">
              <h2 className="text-xl font-bold text-slate-900">
                Upload Your Answer Sheet
              </h2>
              <p className="mt-1.5 text-sm text-slate-500">
                Handwritten or typed · JPEG, PNG, WebP, or PDF · All subjects
              </p>
            </div>
            <UploadForm />
          </div>
        </div>
      </section>

      {/* ── SUPPORTED EXAMS ──────────────────────────────────────────── */}
      <section className="container-pad pb-16">
        <div className="mb-10 text-center">
          <p className="section-label mb-3">Works For</p>
          <h2 className="text-2xl font-bold text-slate-900 sm:text-3xl">
            Every class, every exam, every subject
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            Select your exam type in the form above — the rubric adapts automatically
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {EXAM_CARDS.map((e, i) => (
            <div
              key={e.title}
              className={clsx(
                'anim-in flex items-start gap-4 rounded-2xl border border-slate-100 bg-white p-5',
                'shadow-[0_1px_3px_rgba(0,0,0,0.06)] transition-all duration-300 hover:shadow-md hover:-translate-y-0.5',
              )}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <span className="text-3xl" aria-hidden="true">{e.emoji}</span>
              <div>
                <h3 className="font-semibold text-slate-900">{e.title}</h3>
                <p className="mt-0.5 text-sm text-slate-500">{e.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── HOW IT WORKS ─────────────────────────────────────────────── */}
      <section className="bg-slate-900 py-16">
        <div className="container-pad">
          <div className="mb-10 text-center">
            <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-widest text-white/70">
              How It Works
            </p>
            <h2 className="text-2xl font-bold text-white sm:text-3xl">
              Three steps to a complete evaluation
            </h2>
          </div>

          <div className="grid gap-6 sm:grid-cols-3">
            {HOW_STEPS.map((s, i) => (
              <div
                key={s.title}
                className="anim-in rounded-2xl border border-white/8 bg-white/5 p-6 backdrop-blur-sm"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-2xl ${s.iconBg}`}>
                  <s.icon className={`h-6 w-6 ${s.iconColor}`} />
                </div>
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">
                  Step {i + 1}
                </p>
                <h3 className="mt-1 text-base font-semibold text-white">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{s.desc}</p>
              </div>
            ))}
          </div>

          {/* ── Rubric parameters ── */}
          <div className="mt-16">
            <div className="mb-8 text-center">
              <h2 className="text-xl font-bold text-white">
                Scored on 5 parameters · 10 points each · 50 total
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                Same rubric for every exam — adapted to the level you choose
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {RUBRIC_PARAMS.map((p, i) => (
                <div
                  key={p.name}
                  className="anim-in rounded-2xl border border-white/8 bg-white/5 p-5 backdrop-blur-sm hover:bg-white/10 transition-all duration-300"
                  style={{ animationDelay: `${i * 60}ms` }}
                >
                  <div className="mb-3 flex items-center gap-3">
                    <span className="text-2xl" aria-hidden="true">{p.icon}</span>
                    <h3 className="font-semibold text-white">{p.name}</h3>
                  </div>
                  <p className="text-sm leading-relaxed text-slate-400">{p.desc}</p>
                  <div className="mt-4 flex items-center gap-3">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
                      <div className={`h-full rounded-full ${p.bar}`} style={{ width: '100%' }} />
                    </div>
                    <span className="text-xs font-bold text-slate-400">10 pts</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

    </PageLayout>
  );
}

/* ── Static data ──────────────────────────────────────────────────── */

const FEATURE_PILLS = [
  { icon: Upload,      label: 'Photo · PDF · Image',    colour: 'text-teal-400'    },
  { icon: FileText,    label: 'Any Subject',             colour: 'text-cyan-400'    },
  { icon: BarChart3,   label: 'Detailed Score Sheet',    colour: 'text-violet-300'  },
  { icon: CheckCircle, label: 'Red-Ink Annotations',    colour: 'text-emerald-400' },
];

const EXAM_CARDS = [
  { emoji: '📝', title: 'School Tests (Class 6–8)',      desc: 'Chapter tests, unit tests, class assignments' },
  { emoji: '📖', title: 'Board Prep (Class 9–10)',        desc: 'CBSE, ICSE, and state board answers' },
  { emoji: '🎓', title: 'Senior Board (Class 11–12)',     desc: 'Science, Commerce, Humanities streams' },
  { emoji: '⚙️', title: 'Engineering Entrance (JEE)',    desc: 'Descriptive solutions, derivations, proofs' },
  { emoji: '🩺', title: 'Medical Entrance (NEET)',        desc: 'Biology, anatomy, physiology answers' },
  { emoji: '🏛️', title: 'Civil Services (UPSC)',         desc: 'Essay, GS, optional subject answers' },
  { emoji: '⚖️', title: 'Law Entrance (CLAT)',           desc: 'Legal reasoning and comprehension' },
  { emoji: '🏫', title: 'College / University',           desc: 'Semester exams, term papers, assignments' },
  { emoji: '✏️', title: 'Custom / Any Other Exam',       desc: 'Any handwritten or typed answer sheet' },
];

const HOW_STEPS = [
  {
    icon: Upload, iconBg: 'bg-violet-900/40', iconColor: 'text-violet-400',
    title: 'Upload the answer sheet',
    desc:  'Drag and drop a photo or PDF of any handwritten or typed answer.',
  },
  {
    icon: BarChart3, iconBg: 'bg-teal-900/40', iconColor: 'text-teal-400',
    title: 'Choose the exam type',
    desc:  'Select the class or exam — the rubric adjusts to the right level automatically.',
  },
  {
    icon: FileText, iconBg: 'bg-cyan-900/40', iconColor: 'text-cyan-400',
    title: 'Get a full report',
    desc:  'Scores, red-ink annotations, strengths, improvements, and a downloadable report.',
  },
];

const RUBRIC_PARAMS = [
  {
    name: 'Structure',
    icon: '🏗️',
    desc: 'Clear introduction, organised body, and a conclusion — appropriate for the level.',
    bar:  'bg-gradient-to-r from-violet-500 to-violet-400',
  },
  {
    name: 'Content & Accuracy',
    icon: '📚',
    desc: 'Correct facts, relevant examples, and appropriate depth for the subject and class.',
    bar:  'bg-gradient-to-r from-teal-500 to-teal-400',
  },
  {
    name: 'Language & Expression',
    icon: '✍️',
    desc: 'Grammar, vocabulary, clarity — judged at the expected level of the student.',
    bar:  'bg-gradient-to-r from-cyan-500 to-cyan-400',
  },
  {
    name: 'Relevance to Question',
    icon: '🎯',
    desc: 'Stays on topic, directly addresses what was asked, no filler content.',
    bar:  'bg-gradient-to-r from-amber-500 to-amber-400',
  },
  {
    name: 'Critical Thinking',
    icon: '🧠',
    desc: 'Reasoning, analysis, and original thought beyond memorised facts.',
    bar:  'bg-gradient-to-r from-rose-500 to-rose-400',
  },
];
