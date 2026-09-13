int x = 1 + 2 * (3 + 4);

int main(void) {
    int a = x + 5;
    int x = 5;
    {
      int x = x * a + 7;
      int math = x / 7;
      print(math);
      print(x);
    }
    return 0;
}
