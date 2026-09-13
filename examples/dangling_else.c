int classify(int x) {
    int result;
    result = 0;
    if (x > 0)
        if (x > 100)
            result = 2;
        else
            result = 1;
    print(result);
    return result;
}

int main(void) {
    classify(5);
    classify(150);
    classify(-3);
    return 0;
}
