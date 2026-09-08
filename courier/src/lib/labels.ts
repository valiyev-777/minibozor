/**
 * Every word on the screen, in one file.
 *
 * Uzbek only. The words here are shorter than the other two panels' on
 * purpose: this screen is read at arm's length, outdoors, by somebody holding
 * a parcel, and a sentence they have to stop and read is a sentence in the
 * way.
 *
 * The backend's own text is not repeated. A status word, a delivery window, a
 * refusal reason — those arrive on the row and go on the screen as they are.
 */
export const t = {
  app: "Kuryer",
  today: "Mening ishim",

  // where to go
  board: "Bo'sh zakaslar",
  myWork: "Mening ishim",
  profile: "Profil",

  // the board
  boardEmpty: "Bo'sh zakas yo'q",
  boardEmptyHint: "Ombor zakasni tayyorlaganda shu yerda paydo bo'ladi — istaganini olasiz.",
  take: "Olaman",
  taking: "Olinmoqda…",
  taken: "Zakas sizniki — ombordan olib keting",
  takenByOther: "Bu zakasni boshqa kuryer olib ketdi",
  readyAt: "Ombordan olinadi",
  waiting: "kutmoqda",

  // the profile
  deliveredToday: "Bugun yetkazdim",
  deliveredMonth: "Shu oyda",
  deliveredTotal: "Jami yetkazdim",
  earnedToday: "Bugun ishladim",
  earnedMonth: "Shu oyda",
  earnedTotal: "Jami ishlagan",
  perDelivery: "Bitta yetkazish uchun",
  cashOnHand: "Qo'limdagi naqd",
  cashOnHandHint: "Bu pul ofisga topshiriladi — ishlagan pulingiz emas.",
  failedAttempts: "Yetkazilmagan urinish",
  earningsHint: "Har yetkazilgan zakas uchun belgilangan haq. Naqd pul alohida hisoblanadi.",
  signOut: "Chiqish",
  install: "Ilovani o'rnatish",

  // signing in
  signInTitle: "Kirish",
  phone: "Telefon raqami",
  code: "SMS kod",
  sendCode: "Kod yuborish",
  signIn: "Kirish",
  changePhone: "Raqamni o'zgartirish",
  devCode: "Test kodi",

  // the round
  deliveries: "Yetkazish",
  pickups: "Olib kelish",
  nothingToday: "Bugun vazifa yo'q",
  nothingTodayHint: "\"Bo'sh zakaslar\" bo'limiga o'tib, o'zingizga zakas olasiz.",
  cashDue: "Naqd olinadi",
  paidAlready: "To'langan",
  items: "dona",
  attempts: "urinish",
  lastFailure: "Oxirgi urinish",

  // one stop
  call: "Qo'ng'iroq",
  recipient: "Kim oldi",
  recipientHint: "Tovarni olgan odamning ismi",
  cash: "Olingan naqd pul",
  photo: "Surat",
  addPhoto: "Surat qo'shish",
  photoOptional: "Surat majburiy emas",
  delivered: "Yetkazdim",
  failed: "Yetkaza olmadim",
  failedReason: "Nima bo'ldi?",
  deliveredDone: "Yetkazildi",
  failedDone: "Urinish yozildi",
  cashMustMatch: "Naqd summa aynan mos bo'lishi kerak",
  address: "Manzil",
  window: "Vaqt",

  // a collection
  collect: "Oldim",
  notCollected: "Olmadim",
  collectDone: "Olindi",
  collectHint: "Har manzil bo'yicha belgilang, keyin omborga topshiring",
  sendRun: "Omborga topshirdim",
  customer: "Xaridor",
  reason: "Sabab",
  reasonRequired: "Olinmagan bo'lsa sababini yozing",
} as const
