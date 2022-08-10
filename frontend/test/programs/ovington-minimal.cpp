/* Derived from chess-aces program with MIT license (reproduced below). See also
 * doc/legal.rst
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the “Software”), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <memory>

class FakeBase {
public:
  virtual ~FakeBase(){};
  virtual int other() const;
  virtual int inspect() const;
};

int FakeBase::other() const { return 2; }

int FakeBase::inspect() const { return 1; }

class FakeLambda : public FakeBase {
public:
  FakeLambda(){};
  virtual ~FakeLambda(){};
  virtual int inspect() const;
  int notvirtual() const __attribute__((noinline));
};

__attribute__((noinline, optnone)) int FakeLambda::inspect() const {
  return 42;
}

__attribute__((noinline, optnone)) int FakeLambda::notvirtual() const {
  return 99;
}

__attribute__((noinline)) int hardcoded_stack() {
  FakeLambda mylambda = FakeLambda();
  return mylambda.inspect();
}

__attribute__((noinline)) int hardcoded_ptr() {
  FakeLambda *mylambda = new FakeLambda();
  int i = mylambda->inspect();
  delete mylambda;
  return i;
}

__attribute__((noinline)) int hardcoded_shared() {
  std::shared_ptr<FakeLambda> mylambda = std::make_shared<FakeLambda>();
  return mylambda->inspect();
}

__attribute__((noinline)) int hardcoded_stack_notvirtual() {
  FakeLambda mylambda = FakeLambda();
  return mylambda.notvirtual();
}

__attribute__((noinline)) int hardcoded_ptr_notvirtual() {
  FakeLambda *mylambda = new FakeLambda();
  int i = mylambda->notvirtual();
  delete mylambda;
  return i;
}

__attribute__((noinline)) int hardcoded_shared_notvirtual() {
  std::shared_ptr<FakeLambda> mylambda = std::make_shared<FakeLambda>();
  return mylambda->notvirtual();
}

int main() {
  int a = hardcoded_stack();
  int b = hardcoded_ptr();
  int c = hardcoded_shared();

  int d = hardcoded_stack_notvirtual();
  int e = hardcoded_ptr_notvirtual();
  int f = hardcoded_shared_notvirtual();

  return a + b + c + d + e + f;
}
