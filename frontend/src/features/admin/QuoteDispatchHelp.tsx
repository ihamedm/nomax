import type { ReactNode } from "react";

import { AdminModal } from "./AdminModal";

function Arrow({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center py-0.5" aria-hidden>
      {label && <span className="mb-0.5 text-[9px] text-slate-400">{label}</span>}
      <span className="h-3 w-px bg-slate-300" />
      <span className="-mt-1 text-[9px] leading-none text-slate-300">▼</span>
    </div>
  );
}

function FlowNode({
  step,
  title,
  description,
  chips,
  tone = "slate",
}: {
  step: string;
  title: string;
  description: string;
  chips?: string[];
  tone?: "brand" | "amber" | "slate" | "emerald";
}) {
  const tones = {
    brand: "border-brand-200 bg-brand-50/70",
    amber: "border-amber-200 bg-amber-50/70",
    slate: "border-slate-200 bg-white",
    emerald: "border-emerald-200 bg-emerald-50/60",
  };
  const badges = {
    brand: "bg-brand-600 text-white",
    amber: "bg-amber-500 text-white",
    slate: "bg-slate-700 text-white",
    emerald: "bg-emerald-600 text-white",
  };
  return (
    <div className={`rounded-xl border px-3 py-2.5 ${tones[tone]}`}>
      <div className="flex items-start gap-2.5">
        <span
          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-[10px] font-black ${badges[tone]}`}
        >
          {step}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-black text-slate-800">{title}</p>
          <p className="mt-0.5 text-[10px] leading-5 text-slate-500">{description}</p>
          {chips && chips.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {chips.map((chip) => (
                <span
                  key={chip}
                  className="rounded-md border border-slate-200 bg-white/80 px-1.5 py-0.5 text-[9px] text-slate-500"
                >
                  {chip}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Branch({
  answer,
  tone,
  title,
  description,
}: {
  answer: string;
  tone: "yes" | "no" | "warn";
  title: string;
  description: string;
}) {
  const colors =
    tone === "yes"
      ? "border-emerald-200 bg-emerald-50/70 text-emerald-800"
      : tone === "warn"
        ? "border-amber-200 bg-amber-50/70 text-amber-800"
        : "border-slate-200 bg-slate-50 text-slate-700";
  return (
    <div className={`rounded-lg border px-2.5 py-2 ${colors}`}>
      <p className="text-[9px] font-black">{answer}</p>
      <p className="mt-0.5 text-[10px] font-bold">{title}</p>
      <p className="mt-0.5 text-[9px] leading-4 opacity-80">{description}</p>
    </div>
  );
}

function Decision({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/50 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-amber-500">◆</span>
        <p className="text-[10px] font-black text-amber-800">تصمیم: {title}</p>
      </div>
      <div className="mt-2 grid gap-1.5 sm:grid-cols-2">{children}</div>
    </div>
  );
}

function SectionTitle({
  number,
  title,
  hint,
}: {
  number: string;
  title: string;
  hint: string;
}) {
  return (
    <div className="mb-2 flex items-start gap-2">
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-slate-900 text-[9px] font-black text-white">
        {number}
      </span>
      <div>
        <p className="text-xs font-black text-slate-800">{title}</p>
        <p className="mt-0.5 text-[10px] leading-5 text-slate-400">{hint}</p>
      </div>
    </div>
  );
}

const VARIABLES = [
  {
    group: "اندازه و تعداد موج",
    items: [
      ["تعداد صاحبان در موج اول", "در اولین ارسال، درخواست به چند صاحب کسب‌وکار برود."],
      ["تعداد صاحبان در موج‌های بعد", "هر موج تازه چند صاحب جدید اضافه کند."],
      ["حداقل کسب‌وکار هدف", "اگر گزینه‌های نزدیک کم بودند، برای رسیدن به این تعداد از شعاع یا دسته گسترده‌تر استفاده شود."],
      ["حداکثر تعداد موج", "بعد از این تعداد موج، ارسال خودکار متوقف می‌شود."],
    ],
  },
  {
    group: "زمان و انتظار",
    items: [
      ["بازه پاسخ عادی", "چند دقیقه صبر کنیم و بعد موج بعدی را برای درخواست عادی بفرستیم."],
      ["بازه پاسخ فوری", "همان انتظار، اما کوتاه‌تر برای درخواست فوری."],
      ["بازه جستجوی مجدد", "اگر هیچ کسب‌وکار مناسبی پیدا نشد، هر چند دقیقه دوباره بررسی شود."],
      ["موج بعد پس از مشاهده بدون پیشنهاد", "اگر کسب‌وکار درخواست را دید ولی پیشنهاد نداد، موج بعد ارسال شود یا منتظر بمانیم."],
    ],
  },
  {
    group: "مکان و دسته‌بندی",
    items: [
      ["شعاع اصلی", "اولویت اول: فقط کسب‌وکارهای داخل این شعاع."],
      ["شعاع توسعه", "اگر داخل شعاع اصلی کافی نبود، تا این محدوده گسترش می‌دهیم."],
      ["در نبود زیردسته دقیق، کل دسته بررسی شود", "مثلاً برای «تعمیر یخچال» اگر کسب‌وکار همان زیردسته نبود، از کل دسته «ساختمان و تأسیسات» استفاده شود."],
      ["در نبود گزینه، خارج از شعاع هم ارسال شود", "آخرین لایه پوشش؛ باعث می‌شود درخواست بدون صاحب نماند."],
    ],
  },
  {
    group: "پنجره ارسال",
    items: [
      ["ساعت شروع و پایان ارسال", "ارسال عادی فقط داخل این بازه به وقت تهران انجام می‌شود."],
      ["ارسال درخواست فوری در شب", "درخواست فوری خارج از بازه هم ارسال شود؛ اولویت با کسب‌وکارهای شبانه‌روزی است."],
      ["ارسال خودکار فعال باشد", "کلید اصلی؛ با خاموش شدن آن فقط ارسال دستی مدیر کار می‌کند."],
    ],
  },
];

export function QuoteDispatchHelp({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <AdminModal
      title="راهنمای ارسال استعلام به کسب‌وکارها"
      className="max-w-5xl"
      onClose={onClose}
    >
      <div className="space-y-4">
        <div className="rounded-2xl border border-brand-100 bg-brand-50/60 p-3.5">
          <p className="text-sm font-black text-brand-800">
            یک درخواست، چند موج، بدون جاافتادن
          </p>
          <p className="mt-1 text-[11px] leading-6 text-brand-700/80">
            هدف این استراتژی ساده است: درخواست مشتری به یک گروه کوچک و مرتبط
            برسد؛ اگر در زمان مشخصی واکنشی نیامد، به صاحبان تازه ارسال شود. هیچ
            صاحبی در یک استعلام دو بار پیام نمی‌گیرد و درخواست تا پیدا شدن گزینه
            مناسب در وضعیت فعال می‌ماند.
          </p>
          <div className="mt-2.5 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
            {[
              ["موج اول", "چند صاحب مرتبط"],
              ["بازه پاسخ", "زمان تصمیم‌گیری"],
              ["موج بعدی", "صاحبان تازه"],
              ["سقف موج", "پایان ارسال خودکار"],
            ].map(([title, hint]) => (
              <div key={title} className="rounded-lg bg-white/80 px-2 py-1.5">
                <p className="text-[9px] font-black text-brand-700">{title}</p>
                <p className="mt-0.5 text-[9px] text-slate-500">{hint}</p>
              </div>
            ))}
          </div>
        </div>

        <section>
          <SectionTitle
            number="۱"
            title="مسیر کامل یک درخواست"
            hint="از ثبت مشتری تا پایان ارسال خودکار؛ شاخه‌های «خیر» مسیرهای جایگزین را نشان می‌دهند."
          />
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
            <FlowNode
              step="شروع"
              tone="emerald"
              title="مشتری درخواست را ثبت می‌کند"
              description="دسته، زیردسته، آدرس و فوریت درخواست ذخیره می‌شود. از این لحظه درخواست فعال است."
            />
            <Arrow label="بررسی فوری" />
            <Decision title="الان داخل پنجره ارسال هستیم؟">
              <Branch
                answer="بله"
                tone="yes"
                title="ادامه به انتخاب کسب‌وکار"
                description="ارسال عادی داخل بازه ۶ تا ۲۱ تهران؛ درخواست فوری طبق تنظیم شبانه."
              />
              <Branch
                answer="خیر"
                tone="warn"
                title="زمان‌بندی برای پنجره بعدی"
                description="درخواست در صف می‌ماند و در اولین پنجره مجاز، خودکار ارسال می‌شود."
              />
            </Decision>
            <Arrow label="اگر ارسال مجاز بود" />
            <FlowNode
              step="۲"
              tone="slate"
              title="نردبان تطبیق کسب‌وکارها"
              description="به‌ترتیب اولویت، کسب‌وکارهای تأییدشده بررسی می‌شوند. هر صاحب کسب‌وکار فقط یک بار وارد این استعلام می‌شود."
              chips={[
                "زیردسته دقیق + شعاع اصلی",
                "همان دسته + شعاع اصلی",
                "شعاع توسعه‌یافته",
                "کل دسته در صورت فعال بودن",
              ]}
            />
            <Arrow />
            <Decision title="کاندید واجد شرایط پیدا شد؟">
              <Branch
                answer="بله"
                tone="yes"
                title="ارسال موج"
                description="به اندازه «تعداد صاحبان در موج» و حداقل «کسب‌وکار هدف» انتخاب و پیام می‌شوند."
              />
              <Branch
                answer="خیر"
                tone="warn"
                title="جستجوی مجدد"
                description="درخواست در وضعیت «در حال جستجو» می‌ماند و هر «بازه جستجوی مجدد» دوباره بررسی می‌شود."
              />
            </Decision>
            <Arrow label="موج ارسال" />
            <FlowNode
              step="۳"
              tone="brand"
              title="ارسال به صاحبان انتخاب‌شده"
              description="برای هر کسب‌وکار یک رکورد ارسال و یک پیام درون‌برنامه‌ای ساخته می‌شود. وضعیت «ارسال‌شده» ثبت می‌شود."
              chips={["بدون تکرار صاحب", "پیام درون‌برنامه‌ای", "ثبت موج و منبع ارسال"]}
            />
            <Arrow label="بازه پاسخ" />
            <FlowNode
              step="۴"
              tone="slate"
              title="انتظار و پایش واکنش"
              description="تا پایان بازه پاسخ، مشاهده و پیشنهاد کسب‌وکارها ثبت می‌شود. اگر پیشنهاد برسد، ارسال خودکار همان‌جا متوقف می‌شود."
              chips={["بازه پاسخ عادی", "بازه پاسخ فوری", "مشاهده و پیشنهاد"]}
            />
            <Arrow label="پایان بازه" />
            <Decision title="بعد از بازه پاسخ چه اتفاقی افتاد؟">
              <Branch
                answer="پیشنهاد ثبت شد"
                tone="yes"
                title="توقف ارسال خودکار"
                description="مشتری پیشنهادها را مقایسه می‌کند؛ ارسال به صاحبان جدید متوقف می‌شود."
              />
              <Branch
                answer="هیچ واکنشی نبود"
                tone="warn"
                title="موج بعدی به صاحبان تازه"
                description="اگر سقف موج‌ها پر نشده باشد، موج بعدی ساخته می‌شود."
              />
              <Branch
                answer="فقط مشاهده شد"
                tone="warn"
                title="وابسته به کلید تنظیمات"
                description="اگر «موج بعد پس از مشاهده بدون پیشنهاد» روشن باشد، موج بعدی ارسال می‌شود."
              />
              <Branch
                answer="صاحبی نمانده یا سقف موج پر شد"
                tone="no"
                title="پایان ارسال خودکار"
                description="درخواست همچنان فعال می‌ماند و پیشنهادهای تازه پذیرفته می‌شوند؛ مدیر می‌تواند دستی صاحب اضافه کند."
              />
            </Decision>
            <div className="mt-2 rounded-lg border border-brand-100 bg-white px-2.5 py-2 text-[9px] leading-5 text-slate-500">
              <span className="font-black text-brand-700">مدیر در هر مرحله:</span>{" "}
              می‌تواند از جزئیات استعلام، صاحب کسب‌وکار را دستی اضافه کند یا
              «ارسال موج بعدی» را فوری اجرا کند. این کارها خارج از محدودیت
              دسته‌بندی و شعاع انجام می‌شوند، اما همچنان ثبت و اعلان می‌شوند.
            </div>
          </div>
        </section>

        <section>
          <SectionTitle
            number="۲"
            title="قاعده‌های تصمیم‌گیری"
            hint="برای پیش‌بینی رفتار سیستم، فقط همین پنج قاعده را به خاطر بسپارید."
          />
          <div className="grid gap-2 sm:grid-cols-2">
            {[
              ["پیشنهاد رسید", "ارسال خودکار متوقف می‌شود؛ حتی اگر ظرفیت موج باقی مانده باشد.", "emerald"],
              ["سکوت کامل", "بعد از بازه پاسخ، موج بعدی به صاحبان تازه ارسال می‌شود.", "brand"],
              ["مشاهده بدون پیشنهاد", "به کلید «موج بعد پس از مشاهده بدون پیشنهاد» وابسته است.", "amber"],
              ["هیچ کاندیدی نیست", "درخواست حذف نمی‌شود؛ در وضعیت جستجو می‌ماند و دوباره بررسی می‌شود.", "slate"],
              ["سقف موج یا پایان صاحبان", "ارسال خودکار تمام می‌شود، اما درخواست فعال می‌ماند و پیشنهاد تازه می‌پذیرد.", "slate"],
            ].map(([title, text, tone]) => (
              <div
                key={String(title)}
                className={`rounded-xl border px-3 py-2 ${
                  tone === "emerald"
                    ? "border-emerald-200 bg-emerald-50/60"
                    : tone === "amber"
                      ? "border-amber-200 bg-amber-50/60"
                      : tone === "brand"
                        ? "border-brand-100 bg-brand-50/50"
                        : "border-slate-200 bg-white"
                }`}
              >
                <p className="text-[10px] font-black text-slate-800">{title}</p>
                <p className="mt-0.5 text-[9px] leading-5 text-slate-500">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section>
          <SectionTitle
            number="۳"
            title="هر متغیر چه کاری می‌کند؟"
            hint="نام‌ها دقیقاً همان چیزی است که در همین صفحه تنظیمات می‌بینید."
          />
          <div className="space-y-2">
            {VARIABLES.map((group) => (
              <div key={group.group} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                <div className="border-b border-slate-100 bg-slate-50 px-3 py-1.5 text-[10px] font-black text-slate-600">
                  {group.group}
                </div>
                <div className="divide-y divide-slate-100">
                  {group.items.map(([name, text]) => (
                    <div key={name} className="flex flex-col gap-0.5 px-3 py-1.5 sm:flex-row sm:items-start sm:gap-3">
                      <p className="w-full shrink-0 text-[10px] font-bold text-slate-700 sm:w-52">
                        {name}
                      </p>
                      <p className="text-[9px] leading-5 text-slate-500">{text}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <SectionTitle
            number="۴"
            title="یک مثال واقعی"
            hint="فرض کنید «تعداد صاحبان در موج اول» ۳، «موج‌های بعد» ۲ و «بازه پاسخ» ۲۰ دقیقه باشد."
          />
          <div className="rounded-2xl border border-slate-200 bg-white p-3">
            <div className="relative space-y-2 pr-4">
              <span className="absolute bottom-2 right-[5px] top-2 w-px bg-slate-200" aria-hidden />
              {[
                ["۱۴:۰۰", "درخواست ثبت شد؛ ۳ صاحب کسب‌وکار مرتبط پیام گرفتند."],
                ["۱۴:۲۰", "هیچ‌کس پیشنهاد نداده؛ ۲ صاحب تازه به موج دوم اضافه شدند."],
                ["۱۴:۴۰", "یکی از صاحبان درخواست را دید اما پیشنهاد نداده؛ با روشن بودن کلید مشاهده، موج سوم ارسال می‌شود."],
                ["۱۵:۰۰", "اولین پیشنهاد ثبت شد؛ ارسال خودکار متوقف شد و مشتری پیشنهادها را مقایسه می‌کند."],
              ].map(([time, text]) => (
                <div key={time} className="relative flex items-start gap-2">
                  <span className="absolute right-[-13px] top-1.5 h-2 w-2 rounded-full border-2 border-white bg-brand-500 ring-1 ring-brand-200" />
                  <span className="w-10 shrink-0 text-[9px] font-black text-brand-700" dir="ltr">
                    {time}
                  </span>
                  <p className="text-[9px] leading-5 text-slate-500">{text}</p>
                </div>
              ))}
            </div>
            <p className="mt-2 rounded-lg bg-brand-50 px-2.5 py-1.5 text-[9px] leading-5 text-brand-700">
              اگر در تمام این مدت هیچ پیشنهادی ثبت نشود، پس از پر شدن سقف موج‌ها
              ارسال خودکار متوقف می‌شود؛ اما درخواست مشتری فعال می‌ماند و مدیر
              می‌تواند صاحبان جدید را دستی اضافه کند.
            </p>
          </div>
        </section>

        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-[9px] leading-5 text-slate-500">
            تغییر هر متغیر از موج بعدی اعمال می‌شود و درخواست‌های در حال اجرا را
            متوقف نمی‌کند. برای دیدن جزئیات هر درخواست، از «استعلام‌ها ← جزئیات ←
            گردش ارسال» استفاده کنید.
          </p>
          <button
            type="button"
            onClick={onClose}
            className="h-8 shrink-0 rounded-lg bg-brand-600 px-3 text-[10px] font-bold text-white"
          >
            متوجه شدم
          </button>
        </div>
      </div>
    </AdminModal>
  );
}
