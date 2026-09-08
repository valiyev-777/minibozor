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
  today: "Bugun",
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
  nothingTodayHint: "Operator vazifa berganda shu yerda ko'rinadi.",
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
