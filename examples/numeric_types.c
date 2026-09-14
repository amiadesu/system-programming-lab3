double factorial(int n);

const double EXPECTED_E = 2.718281828459045;

double approximate_e(int terms) {
    double sum = 0.0;
    for (int k = 0; k < terms; k++) {
        sum += 1.0 / factorial(k);
    }
    return sum;
}

double factorial(int n) {
    double result = 1.0;
    while (n > 1) {
        result *= n;
        n--;
    }
    return result;
}

int main(void) {
    print("Наближення e:");
    for (int terms = 1; terms <= 5; terms++) {
        print(approximate_e(terms));
    }

    print("Похибка за 10 членів:");
    double error = EXPECTED_E - approximate_e(10);
    print(error < 0 ? -error : error);

    print("Цілочисельне проти дробового:");
    int a = 7, b = 2;
    print(a / b);
    print(a / (b + 0.0));

    print("Звуження до int:");
    int truncated = 9.99;
    print(truncated);

    return 0;
}