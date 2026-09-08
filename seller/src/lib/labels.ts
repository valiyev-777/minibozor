/**
 * Every word on the screen, in one file.
 *
 * Uzbek only, and that is a decision rather than a stage: this panel is used
 * by shopkeepers in Tashkent and the backend already answers in Uzbek by
 * default. What matters is that the strings are *here* — a screen that spells
 * "Kutilmoqda" its own way is a screen that says something slightly different
 * from the one beside it, and the two drift without anybody deciding to.
 *
 * The backend's own sentences are not repeated here. A refusal reason, a
 * stage label, a status word — those arrive translated on the row
 * (`stage_label`, `inspection_label`, `status_label`) and go on the screen as
 * they are. Copying them would be keeping two answers to one question.
 */

export const t = {
  // the shell
  app: "Sotuvchi kabineti",
  products: "Tovarlarim",
  orders: "Buyurtmalar",
  returns: "Qaytarishlar",
  account: "Hisob",
  signOut: "Chiqish",
  notifications: "Bildirishnomalar",
  noNotifications: "Yangi xabar yo'q",

  // signing in
  signInTitle: "Kabinetga kirish",
  phone: "Telefon raqami",
  code: "SMS kod",
  sendCode: "Kod yuborish",
  signIn: "Kirish",
  changePhone: "Raqamni o'zgartirish",
  devCode: "Test kodi",

  // products
  newProduct: "Yangi tovar",
  productsEmpty: "Hali tovar qo'shmagansiz",
  productsEmptyHint:
    "Tovarni kiritib, omborga topshirasiz. Ombor sanab qabul qilgach, tovar ilovada ko'rinadi.",
  onHand: "Omborda",
  status: "Holat",
  cardDetails: "Tovar ma'lumotlari",
  edit: "Tahrirlash",
  save: "Saqlash",
  cardSaved: "Saqlandi",
  primaryImage: "Asosiy",
  imagesHint: "Birinchi rasm — kartochkaning asosiy rasmi. Kamida bitta kerak.",
  all: "Hammasi",
  searchProducts: "Nomi yoki SKU bo'yicha qidirish",
  nothingFound: "Topilmadi",
  nothingFoundHint: "Boshqa so'z bilan qidirib ko'ring yoki filtrni olib tashlang.",
  declaredShort: "Topshirildi",
  willSend: "Jami omborga topshiriladi",
  stock: "O'lchamlar va soni",
  pieces: "dona",
  inOrder: "buyurtmada",
  totalOnHand: "Jami omborda",
  awaitingCount: "Ombor sanashini kutmoqda. Sanab qabul qilgach, tovar ilovada ko'rinadi.",
  price: "Narx",
  refusalReason: "Rad etish sababi",
  /** Why the *customer* sent it back — not why anybody refused anything. */
  returnReason: "Qaytarish sababi",

  // the form
  title: "Nomi",
  subtitle: "Qisqa izoh",
  description: "Tavsif",
  category: "Kategoriya",
  images: "Rasmlar",
  addImage: "Rasm qo'shish",
  colors: "Ranglar",
  addColor: "Rang qo'shish",
  colorLabel: "Rangni tanlang",
  colorName: "Rang nomi",
  colorNotChosen: "Rang tanlanmagan",
  otherColor: "Boshqa rang",
  removeColor: "Rangni olib tashlash",
  colorPhoto: "Shu rangdagi rasm",
  colorPhotoHint:
    "Majburiy. Xaridor rangni tanlaganda tepadagi rasm shu rasmga o'zgaradi — " +
    "rasmsiz rang tanlansa, xaridor boshqa rangning rasmini ko'rib qoladi.",
  addPhoto: "Rasm qo'shish",
  removePhoto: "Rasmni olib tashlash",
  uploadFailed: "Rasm yuklanmadi",
  colorNeedsPhoto: "Har rangga rasm qo'shing",
  sizes: "O'lchamlar",
  addSize: "O'lcham qo'shish",
  sizeLabel: "O'lcham",
  quantity: "Miqdor",
  weight: "Vazn (gramm)",
  oldPrice: "Eski narx",
  submit: "Omborga topshirish",
  submitting: "Yuborilmoqda…",
  submitHint:
    "Topshirgandan keyin tovar ombor sanog'ini kutadi. Qabul qilinsa — sotuvda, " +
    "rad etilsa — sababi shu yerda yoziladi.",

  // one product
  addMore: "Qo'shimcha topshirish",
  addMoreTitle: "Yana qancha olib kelasiz?",
  takeBack: "Olib ketaman",
  takeBackTitle: "Ombordan qancha olib ketasiz?",
  moreThanOnHand: "Omborda bunchasi yo'q",
  cancel: "Bekor qilish",
  savePrice: "Narxni saqlash",
  priceSaved: "Narx o'zgartirildi",
  supplyDeclared: "Topshiruv e'lon qilindi",
  removalRequested: "Olib ketish so'rovi yuborildi",
  removalReason: "Sabab",
  removalUnsellable: "Sotib bo'lmaydi (buzilgan, muddati o'tgan)",
  removalUnsold: "Sotilmayapti",
  nothingToSend: "Miqdorni kiriting — nol topshiruv emas",
  nothingToTakeBack: "Omborda tovar yo'q",

  // orders
  ordersEmpty: "Buyurtma yo'q",
  ordersEmptyHint: "Tovaringiz sotilganda buyurtma shu yerda ko'rinadi.",
  ordersReadOnly: "Bu ro'yxat faqat ko'rish uchun — buyurtmani ombor va operator yuritadi.",
  customer: "Xaridor",
  items: "Dona",
  total: "Summa",

  // returns
  returnsEmpty: "Qaytarish yo'q",
  returnsEmptyHint: "Xaridor tovarni qaytarsa, ombor tekshiradi va qarorni shu yerda so'raydi.",
  inspection: "Ombor tekshiruvi",
  awaitingInspection: "Ombor tekshirmoqda",
  decideBy: "Qaror muddati",
  decided: "Qaror qabul qilingan",
  relisted: "Sotuvga qaytarildi",
  decisionSaved: "Qaror qabul qilindi",
  decisionOverdue: "Muddat o'tdi — tovar avtomatik sotuvga qo'yiladi",

  // the account
  gross: "Sotildi",
  refunds: "Qaytdi",
  payable: "To'lanadigan",
  commission: "Komissiya",
  fulfilment: "Xizmat",
  storage: "Saqlash",
  notFinal: "Davr tugamagan — raqamlar o'zgarishi mumkin",
  accountLines: "Hisob satrlari",
  accountEmpty: "Hali hisob yo'q",
  accountEmptyHint: "Birinchi savdodan keyin bu yerda sotildi, qaytdi va to'lanadigan ko'rinadi.",
} as const

export const removalStatus: Record<string, string> = {
  requested: "So'rov yuborildi",
  ready: "Tayyor",
  collected: "Olib ketildi",
  cancelled: "Bekor qilindi",
}

/**
 * The stage, in one word, for a filter chip.
 *
 * Short forms of what the server sends in `stage_label`: that field is a
 * phrase meant to be read on a row ("Yig'ildi — kuryer kutilmoqda"), and a
 * chip has room for a word and a number.
 */
export const stageWord: Record<string, string> = {
  rejected: "Rad etilgan",
  awaiting_warehouse: "Kutilmoqda",
  in_warehouse: "Omborda",
  on_sale: "Sotuvda",
  sold_out: "Tugagan",
  archived: "Arxivda",
}
