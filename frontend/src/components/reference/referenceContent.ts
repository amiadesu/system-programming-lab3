/**
 * What the language actually accepts, as data.
 *
 * Kept separate from the component that renders it so that extending the
 * grammar means editing this one list, next to nothing else.
 */

export interface ReferenceEntry {
  code: string;
  note: string;
}

export interface ReferenceSection {
  title: string;
  description?: string;
  entries: ReferenceEntry[];
}

export const SYNTAX_REFERENCE: ReferenceSection[] = [
  {
    title: "Типи та оголошення",
    description: "Два типи значень: ціле та дробове.",
    entries: [
      { code: "int a;", note: "Ціла змінна. Без ініціалізатора починається з нуля." },
      { code: "double x = 1.5;", note: "Дробова змінна, 64-бітна." },
      { code: "int a = 1, b, c = 3;", note: "Кілька змінних в одному оголошенні." },
      { code: "const double PI = 3.14159;", note: "Константа. Ініціалізація обовʼязкова, зміна заборонена." },
      { code: "int x = 9.99;", note: "Звуження до int відкидає дробову частину в бік нуля: буде 9." },
    ],
  },
  {
    title: "Функції",
    description: "Оголошення лише на верхньому рівні. Вкладених функцій немає.",
    entries: [
      { code: "int gcd(int a, int b) { ... }", note: "Визначення. Тіло має повертати значення на всіх шляхах." },
      { code: "void greet(void) { ... }", note: "Функція без результату. Її виклик - лише окремий оператор." },
      { code: "int helper(int n);", note: "Прототип. Мусить мати визначення в тому ж файлі й збігатися з ним." },
      { code: "int main(void) { ... }", note: "Точка входу. Параметрів не приймає." },
    ],
  },
  {
    title: "Оператори керування",
    entries: [
      { code: "if (x > 0) { ... } else { ... }", note: "Гілка else необовʼязкова, звʼязується з найближчим if." },
      { code: "while (i < n) { ... }", note: "Перевірка перед тілом." },
      { code: "do { ... } while (i < n);", note: "Тіло виконується щонайменше раз." },
      { code: "for (int i = 0; i < n; i++) { ... }", note: "Будь-яка з трьох частин може бути порожньою: for (;;)." },
      { code: "break; continue;", note: "Лише всередині циклу." },
      { code: "return x;", note: "У void-функції - return; без значення." },
      { code: "{ int t = 1; ... }", note: "Блок має власну область видимості й може затінювати зовнішні імена." },
    ],
  },
  {
    title: "Оператори у виразах",
    description: "Від найнижчого пріоритету до найвищого, як у C.",
    entries: [
      { code: "=  +=  -=  *=  /=  %=  &=  |=  ^=  <<=  >>=", note: "Присвоєння, правоасоціативне." },
      { code: "?:", note: "Умовний вираз. Тип результату спільний для обох гілок." },
      { code: "||   &&", note: "Логічні. Обчислюються скорочено, результат 1 або 0." },
      { code: "|   ^   &", note: "Побітові. Лише для цілих." },
      { code: "==  !=", note: "Рівність. Результат 1 або 0." },
      { code: "<   >   <=  >=", note: "Порівняння." },
      { code: "<<  >>", note: "Зсуви. Лише для цілих." },
      { code: "+   -   *   /   %", note: "Арифметика. Ділення цілих відкидає дробову частину в бік нуля, % лише для цілих." },
      { code: "-x   !x   ~x   ++x   --x", note: "Унарні. ~ лише для цілих." },
      { code: "x++   x--", note: "Постфіксні. Значенням є старе число." },
      { code: "f(a, b)   (x)", note: "Виклик і групування." },
    ],
  },
  {
    title: "Вивід",
    entries: [
      { code: "print(x);", note: "Ціле друкується як є, дробове - з 6-ма знаками після крапки." },
      { code: 'print("Готово");', note: "Текстовий літерал дозволений лише тут: типу рядка в мові немає." },
      { code: '"рядок\\n з \\t екранами"', note: "Підтримуються \\n, \\t, \\r, \\0, \\\\ та \\\"." },
    ],
  },
  {
    title: "Коментарі",
    entries: [
      { code: "// до кінця рядка", note: "Однорядковий." },
      { code: "/* кілька\\n   рядків */", note: "Блоковий. Вкладення не підтримується." },
    ],
  }
];