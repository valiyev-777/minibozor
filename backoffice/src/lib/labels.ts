/**
 * Every word on the screen, in one file.
 *
 * Uzbek only, and that is a decision rather than a stage: the people at these
 * desks work in Uzbek and the backend already answers in it by default. What
 * matters is that the strings are *here* — a screen that spells "Qabul
 * qilish" its own way says something slightly different from the one beside
 * it, and the two drift without anybody deciding to.
 *
 * The backend's own sentences are not repeated here. A status word, a stage
 * label, a refusal reason, a movement's `kind_label` — those arrive already
 * translated on the row and go on the screen as they are. Copying them would
 * be keeping two answers to one question.
 */

export const t = {
  app: "Backoffice",
  signOut: "Chiqish",
  notifications: "Bildirishnomalar",
  noNotifications: "Yangi xabar yo'q",
  back: "Orqaga",

  // signing in
  signInTitle: "Backoffice'ga kirish",
  phone: "Telefon raqami",
  code: "SMS kod",
  sendCode: "Kod yuborish",
  signIn: "Kirish",
  changePhone: "Raqamni o'zgartirish",
  devCode: "Test kodi",

  // the menu
  overview: "Boshqaruv",
  supplies: "Qabul qilish",
  supply: "Qabul qilish",
  orders: "Buyurtmalar",
  order: "Buyurtma",
  pickups: "Qaytgan tovarlar",
  removals: "Sotuvchiga qaytarish",
  stock: "Qoldiq",
  returns: "Qaytarishlar",
  return_: "Qaytarish",
  sellers: "Sotuvchilar",
  users: "Xodimlar",
  catalog: "Katalog",
  product: "Tovar",

  // the overview
  newOrders: "Yangi buyurtma",
  awaitingSupplies: "Kutilayotgan topshiruv",
  awaitingReturns: "Kutilayotgan qaytarish",
  unpickedOrders: "Yig'ilmagan buyurtma",

  // supplies and receiving
  suppliesEmpty: "Kutilayotgan topshiruv yo'q",
  suppliesEmptyHint: "Sotuvchi tovar topshirsa, shu yerda paydo bo'ladi — sanab qabul qilasiz.",
  seller: "Sotuvchi",
  declared: "E'lon qilingan",
  received: "Qabul qilingan",
  difference: "Farq",
  counted: "Sanoq",
  receiveAll: "Hammasini to'liq",
  clearCounts: "Tozalash",
  accept: "Qabul qilish",
  refuse: "Rad etish",
  refuseReason: "Rad etish sababi",
  refuseHint:
    "Sabab sotuvchiga yoziladi. Agar bu tovarning birinchi partiyasi bo'lsa, " +
    "tovar sotuvga chiqmaydi va shu sabab uning kartochkasida ko'rinadi.",
  received_: "Qabul qilindi",
  refused: "Rad etildi",
  note: "Izoh",
  qualityHint:
    "Sifatsiz yoki kam kelgan tovarni kam sanang — e'lon qilingan son o'zgarmaydi, " +
    "farq shu yerda qoladi.",

  // orders
  ordersEmpty: "Buyurtma yo'q",
  ordersEmptyHint: "Yangi buyurtma tushganda shu yerda ko'rinadi.",
  customer: "Xaridor",
  items: "Dona",
  total: "Summa",
  paid: "To'langan",
  unpaid: "Naqd",
  courier: "Kuryer",
  assignCourier: "Kuryer biriktirish",
  courierAssigned: "Kuryer biriktirildi",
  sequence: "Navbat",
  address: "Manzil",
  window: "Yetkazish vaqti",
  statusMoved: "Holat o'zgartirildi",
  cancelOrder: "Bekor qilish",
  cancelReason: "Bekor qilish sababi",
  all: "Hammasi",

  // returns
  returnsEmpty: "Qaytarish yo'q",
  returnsEmptyHint: "Xaridor qaytarish so'rasa, ariza shu yerda ko'rinadi.",
  approve: "Tasdiqlash",
  reject: "Rad etish",
  refund: "Pulni qaytarish",
  refunded: "Pul qaytarildi",
  restock: "Sotuvga qaytarildi",
  restockAsk: "Tovar qayta sotuvga yaroqlimi?",
  restockYes: "Ha — sotuvga",
  restockNo: "Yo'q — hisobdan chiqariladi",
  inspect: "Tekshirish",
  inspectWhole: "Buzilmagan",
  inspectDamaged: "Buzilgan",
  inspected: "Tekshirildi",
  inspection: "Ombor tekshiruvi",
  sellerDecision: "Sotuvchi qarori",
  awaitingInspection: "Tekshirish kutilmoqda",
  awaitingDecision: "Sotuvchi qarori kutilmoqda",
  onlyAwaiting: "Faqat kutayotganlar",

  // pickups
  pickupsEmpty: "Qaytgan tovar yo'q",
  pickupsEmptyHint: "Tasdiqlangan qaytarishni kuryer olib kelishi shu yerda tuziladi.",
  newPickup: "Yangi yig'uv",
  pickupCreated: "Yig'uv tuzildi",
  pickupReceived: "Tovar omborga qabul qilindi",
  receivePickup: "Omborga qabul qilish",
  collected: "Olindi",

  // removals
  removalsEmpty: "Olib ketish so'rovi yo'q",
  removalsEmptyHint: "Sotuvchi tovarini qaytarib so'rasa, buyruq shu yerda ko'rinadi.",
  prepare: "Yig'ib qo'yish",
  prepared: "Yig'ib qo'yildi",
  collect: "Topshirish",
  handedOver: "Sotuvchiga topshirildi",

  // stock
  stockEmpty: "Harakat yo'q",
  stockEmptyHint: "Kirim, sotuv, qaytish va hisobdan chiqarish shu yerda yoziladi.",
  quantity: "Miqdor",
  balance: "Qoldiq",
  reason: "Sabab",
  who: "Kim",
  when: "Qachon",
  writeOff: "Hisobdan chiqarish",
  writtenOff: "Hisobdan chiqarildi",

  // sellers
  sellersEmpty: "Sotuvchi yo'q",
  newSeller: "Yangi sotuvchi",
  sellerCreated: "Sotuvchi qo'shildi",
  sellerSaved: "Saqlandi",
  name: "Nomi",
  commission: "Komissiya, %",
  active: "Faol",
  standDown: "To'xtatish",
  reinstate: "Qaytarish",
  linkedAccount: "Bog'langan hisob",

  // users
  usersEmpty: "Xodim yo'q",
  search: "Qidirish",
  role: "Rol",
  roleChanged: "Rol o'zgartirildi",
  roleNote: "Izoh",

  // the catalogue
  categories: "Kategoriyalar",
  brands: "Brendlar",
  slug: "Slug",
  parent: "Ustki kategoriya",
  add: "Qo'shish",
  save: "Saqlash",
  remove: "O'chirish",
  removed: "O'chirildi",
  added: "Qo'shildi",
  moderation: "Tovarlar",
  productsWaiting: "Qabul kutayotgan tovarlar",
  editCard: "Tovarni tuzatish",
  editHint:
    "Tahrir — tasdiqlash emas. Tovar sotuvga ombor partiyani qabul qilganda chiqadi.",
  title: "Nomi",
  subtitle: "Qisqa izoh",
  description: "Tavsif",
  badge: "Nishon",
  warranty: "Kafolat",
  saved: "Saqlandi",
} as const

export const supplyStatus: Record<string, string> = {
  declared: "Kutilmoqda",
  received: "Qabul qilindi",
  cancelled: "Rad etildi",
}

export const removalStatus: Record<string, string> = {
  requested: "So'rov yuborildi",
  ready: "Yig'ib qo'yilgan",
  collected: "Topshirildi",
  cancelled: "Bekor qilindi",
}

export const pickupStatus: Record<string, string> = {
  open: "Yo'lda",
  collected: "Kuryerda",
  received: "Omborda",
  cancelled: "Bekor qilindi",
}

export const returnStatus: Record<string, string> = {
  submitted: "Ariza",
  approved: "Tasdiqlangan",
  rejected: "Rad etilgan",
  refunded: "Pul qaytarilgan",
}

export const productStatus: Record<string, string> = {
  draft: "Qoralama",
  moderating: "Sanoq kutilmoqda",
  published: "Sotuvda",
  rejected: "Rad etilgan",
  archived: "Arxivlangan",
}

/**
 * Why a count moved, in words.
 *
 * The one enum the server sends without a label beside it — `MovementOut`
 * carries `kind` and no `kind_label` — so this is the map, and it is the only
 * status vocabulary in this file that is not a fallback for something the row
 * already says.
 */
export const movementKind: Record<string, string> = {
  opening: "Boshlang'ich",
  intake: "Kirim",
  sale: "Sotuv",
  cancel_return: "Bekor qilindi",
  customer_return: "Xaridor qaytardi",
  write_off: "Hisobdan chiqarildi",
  count_adjustment: "Sanoq tuzatildi",
  seller_return: "Sotuvchiga qaytdi",
}

export const roleName: Record<string, string> = {
  customer: "Mijoz",
  admin: "Administrator",
  operator: "Operator",
  warehouse: "Ombor",
  courier: "Kuryer",
  seller: "Sotuvchi",
}
