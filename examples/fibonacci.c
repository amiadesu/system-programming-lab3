int fib(int n) {
    if (n <= 1) {
        return n;
    } else {
        return fib(n - 1) + fib(n - 2);
    }
}

int main(void) {
    int i;
    i = 0;
    while (i < 10) {
        print(fib(i));
        i = i + 1;
    }
    return 0;
}
