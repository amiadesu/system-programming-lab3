int is_prime(int n) {
    if (n < 2) {
        return 0;
    }
    for (int d = 2; d * d <= n; d++) {
        if (n % d == 0) {
            return 0;
        }
    }
    return 1;
}

int popcount(int value) {
    int bits = 0;
    do {
        bits += value & 1;
        value >>= 1;
    } while (value > 0);
    return bits;
}

int main(void) {
    int found = 0, n = 0;

    for (n = 2; n <= 30; n++) {
        if (!is_prime(n)) {
            continue;
        }
        print(n);
        found++;
        if (found >= 10) {
            break;
        }
    }

    print(found);

    int a = 6, b = 3;
    print(a & b);
    print(a | b);
    print(a ^ b);
    print(a << 2);
    print(popcount(255));
    print(a > b && b > 0 ? a - b : b - a);

    return 0;
}