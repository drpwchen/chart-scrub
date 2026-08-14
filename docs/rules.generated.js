// GENERATED FILE — do not edit.
// Source of truth: clinic_deid/rules.py
// Regenerate: python tools/export_rules_js.py

export const RULES = [
  {
    name: "mrn",
    description: "Chart/medical record number introduced by a label",
    pattern: new RegExp("(病歷號碼?|病歷|案號|掛號號?碼?)[\\s:：#]*[A-Z]?\\d{5,10}", "g"),
    replacement: "$1[病歷號]",
  },
  {
    name: "roc_id",
    description: "ROC national ID and new-style resident certificate number",
    pattern: new RegExp("(?<![A-Za-z0-9])[A-Z]\\d{9}(?!\\d)", "g"),
    replacement: "[身分證號]",
  },
  {
    name: "nhi_card",
    description: "NHI card number when the surrounding text names it",
    pattern: new RegExp("(?<![A-Za-z0-9])(?:0{4}|[0-9]{4})-?[0-9]{4}-?[0-9]{4}(?=\\s*(?:健保卡|卡號))", "g"),
    replacement: "[健保卡號]",
  },
  {
    name: "mobile",
    description: "Mobile phone number",
    pattern: new RegExp("(?<!\\d)09\\d{2}[-\\s]?\\d{3}[-\\s]?\\d{3}(?!\\d)", "g"),
    replacement: "[電話]",
  },
  {
    name: "landline",
    description: "Landline phone number",
    pattern: new RegExp("(?<!\\d)0\\d{1,2}[-\\s]?\\d{3,4}[-\\s]?\\d{4}(?!\\d)", "g"),
    replacement: "[電話]",
  },
  {
    name: "email",
    description: "Email address",
    pattern: new RegExp("(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", "g"),
    replacement: "[電子郵件]",
  },
  {
    name: "birth_roc",
    description: "Date of birth written in ROC calendar form",
    pattern: new RegExp("民國\\s?\\d{1,3}\\s?年\\s?\\d{1,2}\\s?月\\s?\\d{1,2}\\s?[日號](?:\\s?出?生)?", "g"),
    replacement: "[生日]",
  },
  {
    name: "birth_labelled",
    description: "Date of birth introduced by a label",
    pattern: new RegExp("(生日|出生)[是為:：\\s]*[\\d/年月日號\\s-]{4,12}", "g"),
    replacement: "$1[生日]",
  },
  {
    name: "address",
    description: "Full address starting from one of the 22 counties/cities",
    pattern: new RegExp("(?:臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|新竹市|新竹縣|嘉義市|嘉義縣|苗栗縣|彰化縣|南投縣|雲林縣|屏東縣|宜蘭縣|花蓮縣|臺東縣|台東縣|澎湖縣|金門縣|連江縣)(?:[一-鿿]{1,3}[區鄉鎮市])?(?:[一-鿿0-9]{0,12}[路街道巷弄](?:[一二三四五六七八九十0-9]{1,3}段)?(?:[0-9之\\-]{1,8}[號巷弄])?(?:[0-9之\\-]{1,6}[樓F])?)?", "g"),
    replacement: "[地址]",
  },
  {
    name: "street_number",
    description: "Street address without a county prefix, anchored on a house number",
    pattern: new RegExp("(^|[，,。；;：:\\s]|住址|地址|住在|居住|位於|住|在)[一-鿿0-9]{2,5}[路街道](?:[一二三四五六七八九十0-9]{1,3}段)?[0-9之\\-]{1,8}[號巷](?:[0-9之\\-]{1,6}[樓F])?", "gm"),
    replacement: "$1[地址]",
  },
  {
    name: "surname_title",
    description: "Surname followed by a form of address (陳先生, 林阿嬤)",
    pattern: new RegExp("[陳林黃張李王吳劉蔡楊許鄭謝郭洪曾邱廖賴徐周葉蘇莊呂江何蕭羅高潘簡朱鍾游彭詹胡施沈余盧梁趙顏柯翁魏孫戴范方宋鄧杜傅侯曹薛丁卓阮馬董溫唐藍蔣石古紀姚連馮歐程湯田康姜白汪鄒尤巫鐘黎涂龔嚴韓](?:先生|小姐|太太|女士|阿公|阿嬤|阿伯|阿姨|大哥|大姐|同學|老師|伯伯|奶奶|爺爺)", "g"),
    replacement: "[稱謂]",
  },
  {
    name: "fullname_title",
    description: "Full name followed by a form of address (陳小明先生)",
    pattern: new RegExp("[陳林黃張李王吳劉蔡楊許鄭謝郭洪曾邱廖賴徐周葉蘇莊呂江何蕭羅高潘簡朱鍾游彭詹胡施沈余盧梁趙顏柯翁魏孫戴范方宋鄧杜傅侯曹薛丁卓阮馬董溫唐藍蔣石古紀姚連馮歐程湯田康姜白汪鄒尤巫鐘黎涂龔嚴韓][一-鿿]{1,2}(?:先生|小姐|太太|女士|阿公|阿嬤|阿伯|阿姨|大哥|大姐|同學|老師|伯伯|奶奶|爺爺)", "g"),
    replacement: "[姓名]",
  },
  {
    name: "relation_name",
    description: "Family relation word immediately followed by a name (我太太林美玉)",
    pattern: new RegExp("(太太|先生|老公|老婆|兒子|女兒|媽媽|爸爸|母親|父親|哥哥|姊姊|姐姐|弟弟|妹妹|孫子|孫女|媳婦|女婿|外甥|姪子|姪女|阿姨|舅舅|叔叔)[陳林黃張李王吳劉蔡楊許鄭謝郭洪曾邱廖賴徐周葉蘇莊呂江何蕭羅高潘簡朱鍾游彭詹胡施沈余盧梁趙顏柯翁魏孫戴范方宋鄧杜傅侯曹薛丁卓阮馬董溫唐藍蔣石古紀姚連馮歐程湯田康姜白汪鄒尤巫鐘黎涂龔嚴韓][一-鿿]{1,2}", "g"),
    replacement: "$1[姓名]",
  },
  {
    name: "declared_name",
    description: "Name introduced by an explicit declaration",
    pattern: new RegExp("(我叫|我是|名字是|姓名[是為:：\\s]|病人叫|他叫|她叫|叫做)\\s*[一-鿿]{2,4}", "g"),
    replacement: "$1[姓名]",
  },
  {
    name: "role_name",
    description: "Role word immediately followed by a full name (病人陳小明)",
    pattern: new RegExp("(病人|患者|個案|案主|家屬)[陳林黃張李王吳劉蔡楊許鄭謝郭洪曾邱廖賴徐周葉蘇莊呂江何蕭羅高潘簡朱鍾游彭詹胡施沈余盧梁趙顏柯翁魏孫戴范方宋鄧杜傅侯曹薛丁卓阮馬董溫唐藍蔣石古紀姚連馮歐程湯田康姜白汪鄒尤巫鐘黎涂龔嚴韓][一-鿿]{1,2}", "g"),
    replacement: "$1[姓名]",
  },
  {
    name: "english_name",
    description: "English personal name after an explicit cue",
    pattern: new RegExp("(name is|Mr\\.|Mrs\\.|Ms\\.)\\s+[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)?", "g"),
    replacement: "$1 [NAME]",
  },
];

// Mirrors clinic_deid.rules.normalize(): full-width digits and Latin letters
// fold to half-width, punctuation is left alone.
export function normalize(text) {
  return text.replace(/[０-９Ａ-Ｚａ-ｚ]/g,
    c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0));
}

// Mirrors clinic_deid.rules.deidentify_verbose().
export function deidentify(text, { normalize: doNormalize = true } = {}) {
  if (doNormalize) text = normalize(text);
  const hits = {};
  for (const rule of RULES) {
    rule.pattern.lastIndex = 0;
    const before = text;
    text = text.replace(rule.pattern, rule.replacement);
    if (text !== before) {
      const matches = before.match(rule.pattern);
      hits[rule.name] = matches ? matches.length : 1;
    }
  }
  return { text, hits };
}
