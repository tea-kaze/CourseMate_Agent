# Java：面向对象与核心基础（演示资料）

## 1. Java 平台与运行机制

Java 通过“源代码 → 字节码 → JVM 执行”实现跨平台：`.java` 源文件由 javac 编译成平台无关的 `.class` 字节码，字节码由各平台的 JVM 解释执行或即时编译（JIT），因此可以“一次编写，到处运行”。

- JVM（Java 虚拟机）：负责运行字节码、内存管理与垃圾回收；
- JRE（Java 运行时环境）：JVM 加核心类库；
- JDK（Java 开发工具包）：JRE 加 javac 等开发工具。

程序入口示例：

```java
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello, Java");
    }
}
```

内存区域：栈存放局部变量与方法调用帧，堆存放对象实例；对象不再被引用时由垃圾回收器（GC）自动回收，程序员无需手动释放内存。

## 2. 基本语法与数据类型

八种基本类型：byte、short、int、long、float、double、char、boolean。基本类型直接存值，引用类型（类、接口、数组）存放对象的引用地址。自动装箱/拆箱指基本类型与包装类之间自动转换，例如 `Integer n = 42;`。

String 是不可变对象，相同字面量会被字符串常量池缓存；频繁拼接字符串时应使用 StringBuilder 或 StringBuffer。控制流包括 if/else、switch、for、while、do-while。数组长度固定，例如 `int[] arr = new int[10];`。

## 3. 面向对象三大特性

封装：用 private 隐藏字段，通过公共的 getter/setter 暴露访问入口，控制数据被修改的方式，提高安全性与可维护性。

继承：子类用 extends 继承父类，通过 super 调用父类构造器或方法；方法重写（@Override）要求方法签名一致且访问权限不能变窄。构造器调用顺序：先父类构造器，再子类构造器。

多态：父类引用可以指向子类对象（向上转型），调用方法时按对象的运行时类型动态绑定；重载（同一类中方法名相同、参数列表不同）与重写（子类覆盖父类方法）是两个不同概念。

抽象类与接口：

- 抽象类（abstract class）可以有字段、具体方法和抽象方法，适合“is-a”且需要共享实现的场景，只能单继承；
- 接口（interface）强调“can-do”能力契约，可以多实现；Java 8 起接口可以定义 default 和 static 方法。

示例：

```java
interface Flyable {
    void fly();
}

abstract class Animal {
    abstract void speak();
}

class Bird extends Animal implements Flyable {
    @Override
    public void speak() {
        System.out.println("叽叽");
    }

    @Override
    public void fly() {
        System.out.println("飞翔");
    }
}
```

## 4. 异常处理

异常体系：Throwable 分为 Error 与 Exception。Error 表示严重问题（如 OutOfMemoryError），程序通常无法处理；Exception 分为受检异常（编译期必须声明或捕获，如 IOException）与非受检异常（运行时异常 RuntimeException，如 NullPointerException）。

```java
try (BufferedReader reader = new BufferedReader(new FileReader("a.txt"))) {
    String line = reader.readLine();
} catch (IOException e) {
    e.printStackTrace();
}
```

try-with-resources 可以自动关闭实现了 AutoCloseable 的资源；finally 块用于必须执行的清理；自定义异常继承 Exception 或 RuntimeException。

## 5. 集合框架与泛型

集合体系：Collection 接口（List、Set、Queue）与 Map 接口。

- List：有序且允许重复。ArrayList 基于动态数组，随机访问快、中间增删慢；LinkedList 基于双向链表，两端增删快、随机访问慢。
- Set：不允许重复。HashSet 基于哈希表，依赖 equals 与 hashCode 判重；TreeSet 按自然顺序或比较器排序。
- Map：键值对集合。HashMap 基于“数组 + 链表/红黑树”，键通过 hashCode 定位桶、equals 判等，负载因子达到 0.75 时扩容；LinkedHashMap 保持插入顺序；ConcurrentHashMap 提供线程安全。

泛型提供编译期类型安全，例如 `List<String>` 只能存放 String；通配符 `? extends T` 表示上界、`? super T` 表示下界；泛型信息在运行时会被类型擦除。

## 6. Object 与常用方法

Object 是 Java 所有类的根类：equals 默认比较对象地址，重写 equals 时必须同时重写 hashCode（两个相等的对象 hashCode 必须相同），否则 HashSet、HashMap 的判重行为会异常；toString 用于返回对象的文本表示。

常用类：StringBuilder / StringBuffer 表示可变字符串（后者线程安全）；包装类提供缓存（如 Integer 缓存 -128 到 127）与解析方法（如 Integer.parseInt）；Math 提供常用数学运算（abs、max、pow、sqrt 等）。

