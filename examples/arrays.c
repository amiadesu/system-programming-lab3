int length_of(int values[], int count);

int fill_squares(int values[], int count) {
    for (int i = 0; i < count; i++) {
        values[i] = i * i;
    }
    return count;
}

int sum_of(int values[], int count) {
    int total = 0;
    for (int i = 0; i < count; i++) {
        total += values[i];
    }
    return total;
}

int max_of(int values[], int count) {
    int best = values[0];
    for (int i = 1; i < count; i++) {
        if (values[i] > best) {
            best = values[i];
        }
    }
    return best;
}

int length_of(int values[], int count) {
    return count;
}

int main(void) {
    int squares[8];
    int count = sizeof(squares) / sizeof(squares[0]);

    print("Кількість елементів:");
    print(count);

    fill_squares(squares, count);
    print("Сума квадратів:");
    print(sum_of(squares, count));
    print("Максимум:");
    print(max_of(squares, count));

    squares[0] = 100;
    print(max_of(squares, length_of(squares, count)));

    print("Решето Ератосфена до 20:");
    int sieve[21];
    for (int i = 0; i < 21; i++) {
        sieve[i] = 1;
    }
    for (int n = 2; n * n <= 20; n++) {
        if (sieve[n]) {
            for (int multiple = n * n; multiple <= 20; multiple += n) {
                sieve[multiple] = 0;
            }
        }
    }
    for (int n = 2; n <= 20; n++) {
        if (sieve[n]) {
            print(n);
        }
    }

    double weights[3];
    weights[0] = 1.5;
    weights[1] = weights[0] * 2;
    weights[2] = weights[1] - weights[0];
    print("Дробовий масив:");
    print(weights[2]);
    print(sizeof(weights));

    return 0;
}