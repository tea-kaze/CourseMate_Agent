# Java：面向对象与核心基础（演示资料）

## 1. Java 平台与运行机制

Java 通过“源代码 → 字节码 → JVM 执行”实现跨平台：`.java` 源文件由 javac 编译成平台无关的 `.class` 字节码，字节码由各平台的 JVM 解释执行或即时编译（JIT），因此可以“一次编写，到处运行”。

完整的编译与运行流程是：先用 `javac` 把 `.java` 源文件编译成字节码 `.class` 文件，再由 JVM 的类加载器把字节码加载进内存，经过字节码校验后交给执行引擎解释执行或 JIT 编译成机器码。JVM 先以解释方式快速启动，检测到热点代码后通过 JIT 编译成机器码缓存，这就是“解释 + 编译”混合执行模式，兼顾启动速度与运行性能。

三大组件：

- JVM（Java 虚拟机）：负责运行字节码、内存管理与垃圾回收，是跨平台的核心；
- JRE（Java 运行时环境）：JVM 加核心类库，用于运行 Java 程序；
- JDK（Java 开发工具包）：JRE 加 javac、jar 等开发工具，用于开发 Java 程序。

类加载器采用双亲委派模型，按层级分为启动类加载器（Bootstrap，加载 JDK 核心类）、平台类加载器（Platform，加载扩展类库）和应用类加载器（Application，加载用户类路径下的类）。加载一个类时先委托给父加载器，父加载器能加载则不再由子加载器加载，这样保证核心类不被篡改。

程序入口示例：

```java
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello, Java");
    }
}
```

编译运行命令：

```bash
javac Hello.java   # 生成 Hello.class
java Hello         # 由 JVM 执行 main 方法
```

内存区域：栈存放局部变量与方法调用帧，堆存放对象实例；对象不再被引用时由垃圾回收器（GC）自动回收，程序员无需手动释放内存，这与 C/C++ 需要手动 free/delete 形成鲜明对比。

## 2. 基本语法与数据类型

八种基本类型：byte、short、int、long、float、double、char、boolean。基本类型直接存值，引用类型（类、接口、数组）存放对象的引用地址。

各基本类型的占用空间与取值范围：

| 类型 | 字节数 | 取值范围 |
| --- | --- | --- |
| byte | 1 | -128 ~ 127 |
| short | 2 | -32768 ~ 32767 |
| int | 4 | 约 ±21 亿 |
| long | 8 | 约 ±9.2 × 10^18 |
| float | 4 | 单精度浮点 |
| double | 8 | 双精度浮点 |
| char | 2 | 单个 Unicode 字符 |
| boolean | 1（逻辑上） | true / false |

类型转换分自动转换与强制转换：小范围类型向大范围类型转换可自动完成（如 byte → int → long → float → double），反之需要强制转换（如 `(int) 3.14`），强制转换可能丢失精度。

自动装箱/拆箱指基本类型与包装类之间自动转换，例如 `Integer n = 42;` 实际是 `Integer n = Integer.valueOf(42);`。注意包装类的缓存机制：Integer 缓存了 -128 到 127 的对象，范围内用 `==` 比较会相等，范围外则可能不相等，比较值应统一用 `equals`。

```java
int a = 100;
Integer b = 100;      // 自动装箱，命中缓存
System.out.println(a == b);        // true（拆箱后比较值）
Integer x = 200;
Integer y = 200;      // 超出缓存范围
System.out.println(x == y);        // false（比较对象地址）
System.out.println(x.equals(y));   // true
```

String 是不可变对象，相同字面量会被字符串常量池缓存，所以 `"abc" == "abc"` 为 true，而 `new String("abc") == "abc"` 为 false。频繁拼接字符串时应使用 StringBuilder（线程不安全但快）或 StringBuffer（线程安全）。

```java
String s = "Hello";
s = s + " World";     // 底层创建了新对象，原 "Hello" 不变
StringBuilder sb = new StringBuilder();
sb.append("Hello").append(" World");  // 原地追加，避免反复创建对象
```

控制流包括 if/else、switch、for、while、do-while。Java 14 起 switch 支持箭头语法与 yield 返回值。数组长度固定，例如 `int[] arr = new int[10];`。

## 3. 面向对象三大特性

**封装**：用 private 隐藏字段，通过公共的 getter/setter 暴露访问入口，控制数据被修改的方式，提高安全性与可维护性。

```java
public class Student {
    private String name;
    private int age;

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public int getAge() { return age; }
    public void setAge(int age) {
        if (age < 0) throw new IllegalArgumentException("年龄不能为负");
        this.age = age;
    }
}
```

**继承**：子类用 extends 继承父类，通过 super 调用父类构造器或方法。构造器调用顺序是先父类构造器、再子类构造器；方法重写（@Override）要求方法签名一致且访问权限不能变窄（不能把 public 改成 private）。

```java
class Animal {
    protected String name;
    public Animal(String name) { this.name = name; }
    public void speak() { System.out.println(name + " 发出声音"); }
}

class Dog extends Animal {
    public Dog(String name) { super(name); }   // 调用父类构造器
    @Override
    public void speak() { System.out.println(name + " 汪汪叫"); }
}
```

**多态**：父类引用可以指向子类对象（向上转型），调用方法时按对象的运行时类型动态绑定，即“编译看左边、运行看右边”。

```java
Animal animal = new Dog("旺财");   // 向上转型
animal.speak();                     // 输出 "旺财 汪汪叫"，动态绑定到 Dog
```

重载（同一类中方法名相同、参数列表不同）与重写（子类覆盖父类方法）是两个不同概念：重载是编译期静态分派，重写是运行期动态分派。

**抽象类与接口**：

- 抽象类（abstract class）可以有字段、具体方法和抽象方法，适合“is-a”且需要共享实现的场景，只能单继承；
- 接口（interface）强调“can-do”能力契约，可以多实现；Java 8 起接口可以定义 default 和 static 方法。

```java
interface Flyable {
    void fly();
    default void land() { System.out.println("降落"); }  // Java 8 默认方法
}

abstract class Animal {
    abstract void speak();
}

class Bird extends Animal implements Flyable {
    @Override public void speak() { System.out.println("叽叽"); }
    @Override public void fly() { System.out.println("飞翔"); }
}
```

## 4. 异常处理

异常体系：Throwable 分为 Error 与 Exception。Error 表示严重问题（如 OutOfMemoryError、StackOverflowError），程序通常无法处理；Exception 分为受检异常（编译期必须声明或捕获，如 IOException、SQLException）与非受检异常（运行时异常 RuntimeException，如 NullPointerException、ArrayIndexOutOfBoundsException）。

完整的异常处理结构是 try-catch-finally，可以有多个 catch 分别捕获不同异常类型（子类异常写在前面），finally 块无论是否抛异常都会执行，常用于释放资源。

```java
public class Demo {
    public static void main(String[] args) {
        try {
            int result = 10 / 0;                 // 抛出 ArithmeticException
        } catch (ArithmeticException e) {
            System.out.println("除数不能为 0: " + e.getMessage());
        } finally {
            System.out.println("始终执行");
        }
    }
}
```

try-with-resources 可以自动关闭实现了 AutoCloseable 的资源，避免手动在 finally 中关闭。

```java
try (BufferedReader reader = new BufferedReader(new FileReader("a.txt"))) {
    String line = reader.readLine();
} catch (IOException e) {
    e.printStackTrace();
}
```

自定义异常继承 Exception（受检）或 RuntimeException（非受检），可以携带自定义错误码或信息；异常链通过构造器的 cause 参数保留原始异常，便于排查根因。

```java
class BusinessException extends RuntimeException {
    public BusinessException(String message) { super(message); }
}

public class Demo {
    public static void main(String[] args) {
        try {
            throw new BusinessException("库存不足");
        } catch (BusinessException e) {
            System.out.println(e.getMessage());
        }
    }
}
```

## 5. 集合框架与泛型

集合体系：Collection 接口（List、Set、Queue）与 Map 接口。选择集合时要根据「是否允许重复、是否有序、读写性能」来决定。

- List：有序且允许重复。ArrayList 基于动态数组，随机访问快、中间增删慢；LinkedList 基于双向链表，两端增删快、随机访问慢。
- Set：不允许重复。HashSet 基于哈希表，依赖 equals 与 hashCode 判重；TreeSet 按自然顺序或比较器排序。
- Map：键值对集合。HashMap 基于“数组 + 链表/红黑树”，键通过 hashCode 定位桶、equals 判等；当链表长度超过 8 且数组长度超过 64 时链表转红黑树；负载因子达到 0.75 时扩容为原来的 2 倍。LinkedHashMap 保持插入顺序；ConcurrentHashMap 采用分段锁 + CAS 提供线程安全。

```java
import java.util.*;

List<String> list = new ArrayList<>();
list.add("Java");
list.add("Python");
list.add("Java");            // 允许重复
System.out.println(list);    // [Java, Python, Java]

Set<String> set = new HashSet<>(list);
System.out.println(set);     // [Java, Python]，去重

Map<String, Integer> map = new HashMap<>();
map.put("Java", 1995);
map.put("Python", 1991);
System.out.println(map.get("Java"));  // 1995
```

泛型提供编译期类型安全，例如 `List<String>` 只能存放 String，运行前就能发现类型错误。泛型类、泛型接口、泛型方法用 `<T>` 声明；通配符 `? extends T` 表示上界（只能读）、`? super T` 表示下界（只能写）；泛型信息在运行时会被类型擦除，所以 `List<String>` 和 `List<Integer>` 在运行时的 Class 是同一个。

```java
class Box<T> {
    private T value;
    public void set(T value) { this.value = value; }
    public T get() { return value; }
}

Box<String> box = new Box<>();
box.set("hello");
String s = box.get();   // 无需强制转换
```

## 6. Object 与常用方法

Object 是 Java 所有类的根类，常用方法有 equals、hashCode、toString。

- equals 默认比较对象地址（等价于 `==`），子类重写 equals 用于比较内容；
- 重写 equals 时必须同时重写 hashCode：两个相等的对象 hashCode 必须相同，否则在 HashSet、HashMap 中会找不到或出现重复，违反容器约定；
- toString 默认返回「类名@哈希码」，重写后返回可读的对象描述。

```java
class User {
    private int id;
    private String name;
    public User(int id, String name) { this.id = id; this.name = name; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        User user = (User) o;
        return id == user.id && Objects.equals(name, user.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, name);
    }

    @Override
    public String toString() {
        return "User{id=" + id + ", name='" + name + "'}";
    }
}
```

常用类：

- String 提供 split、substring、indexOf、replace、equals 等大量字符串处理方法；
- StringBuilder / StringBuffer 表示可变字符串，前者线程不安全但快，后者线程安全（方法加 synchronized）；
- 包装类提供缓存（如 Integer 缓存 -128 到 127）与解析方法（如 Integer.parseInt）；
- Math 提供常用数学运算（abs、max、pow、sqrt 等），Random 用于生成随机数。

## 7. 多线程与并发

线程的创建方式有三种：

- 继承 Thread 类并重写 run 方法；
- 实现 Runnable 接口（更推荐：Java 单继承限制，解耦任务与线程）；
- 实现 Callable 接口，配合 FutureTask 或线程池可获取返回值并抛出异常。

```java
// 方式一：继承 Thread
class MyThread extends Thread {
    @Override public void run() { System.out.println(Thread.currentThread().getName()); }
}
new MyThread().start();

// 方式二：实现 Runnable（推荐）
new Thread(() -> System.out.println("Runnable 运行")).start();

// 方式三：Callable + FutureTask 获取返回值
Callable<Integer> task = () -> { return 42; };
FutureTask<Integer> futureTask = new FutureTask<>(task);
new Thread(futureTask).start();
Integer result = futureTask.get();   // 阻塞等待结果
```

线程的生命周期：新建（NEW）、就绪/运行（RUNNABLE）、阻塞（BLOCKED/WAITING/TIMED_WAITING）、终止（TERMINATED）。start() 使线程进入就绪态等待 CPU 调度，run() 执行完后进入终止态。

synchronized 用于实现同步：修饰实例方法时锁是当前对象（this），修饰静态方法时锁是类的 Class 对象，修饰代码块时可显式指定锁对象；锁是可重入的，即一个线程可以重复获取自己已持有的锁。

```java
class Counter {
    private int count = 0;
    public synchronized void increment() {   // 锁是 this
        count++;
    }
}
```

volatile 关键字保证变量可见性并禁止指令重排，但不保证原子性，适合“一写多读”的场景，不适合 `i++` 这类复合操作。Lock 接口（如 ReentrantLock）比 synchronized 更灵活：支持公平锁、可中断获取锁、tryLock 尝试获取，但需要手动在 finally 中释放锁。

```java
ReentrantLock lock = new ReentrantLock();
try {
    lock.lock();
    // 临界区
} finally {
    lock.unlock();   // 必须在 finally 中释放
}
```

线程池通过 ThreadPoolExecutor 创建，核心参数有核心线程数（corePoolSize）、最大线程数（maximumPoolSize）、空闲存活时间（keepAliveTime）、工作队列（workQueue）与拒绝策略（handler）。使用线程池可复用线程、控制并发量、降低频繁创建销毁线程的开销。Executors 提供便捷工厂方法，但阿里规约推荐手动 new ThreadPoolExecutor 以便明确参数。

```java
ExecutorService pool = Executors.newFixedThreadPool(4);
pool.submit(() -> System.out.println("任务执行"));
pool.shutdown();
```

常用并发工具类：CountDownLatch（等待一组任务完成）、CyclicBarrier（一组线程互相等待到齐）、Semaphore（信号量，控制同时访问资源的线程数）、ThreadLocal（线程本地变量，每个线程独立副本，常用于保存数据库连接、用户上下文）。

## 8. JVM 内存结构与垃圾回收

JVM 运行时数据区：

- 程序计数器：记录当前线程执行的字节码行号，线程私有，是唯一不会发生 OOM 的区域；
- 虚拟机栈：存放局部变量、操作数栈、方法出口，每个方法对应一个栈帧，线程私有；
- 本地方法栈：为本地方法服务；
- 堆：存放对象实例，线程共享，是 GC 的主要区域，也是 OOM 最常见的来源；
- 方法区（JDK 8 起为元空间 Metaspace）：存放类信息、常量、静态变量，线程共享。

堆内存分代：新生代（Eden 区 + 两个 Survivor 区 S0/S1，默认 8:1:1）与老年代。对象先在 Eden 分配，经历多次 Minor GC 后仍存活的对象晋升到老年代；大对象可能直接进入老年代。Minor GC 只回收新生代，Full GC 回收整个堆和方法区，停顿更长。

垃圾回收算法：

- 标记-清除：标记存活对象后清除未标记对象，会产生内存碎片；
- 复制：把存活对象复制到另一块内存后清空原区域，无碎片但浪费一半空间，用于新生代（对象存活率低）；
- 标记-整理：标记后把存活对象向一端移动以消除碎片，用于老年代。

常见垃圾收集器：Serial（单线程，适合单核小内存）、Parallel（多线程，吞吐量优先）、CMS（并发标记清除，低停顿，已废弃）、G1（分 Region 管理，兼顾吞吐与停顿，JDK 9 起默认）、ZGC 与 Shenandoah（低延迟，目标停顿 10ms 内）。

判断对象是否可回收：引用计数法（有循环引用问题，Java 未采用）与可达性分析（从 GC Roots 出发不可达即回收）。GC Roots 包括虚拟机栈中的引用、静态变量、常量、JNI 引用等。引用类型分强引用、软引用（SoftReference，内存不足时回收）、弱引用（WeakReference，下次 GC 就回收）、虚引用（PhantomReference，仅用于跟踪对象回收）。

## 9. 反射与注解

反射：运行时动态获取类信息并操作类的能力，核心类有 Class、Field、Method、Constructor。通过 Class.forName、对象的 getClass 或类字面量（类名.class）获取 Class 对象。反射常用于框架开发（如 Spring 的依赖注入），但性能低于直接调用，且会破坏封装。

```java
// 获取 Class 对象
Class<?> clazz = Class.forName("com.example.User");

// 获取构造器并实例化
Constructor<?> constructor = clazz.getConstructor(String.class);
Object obj = constructor.newInstance("张三");

// 获取并调用方法
Method method = clazz.getMethod("getName");
Object result = method.invoke(obj);      // 调用 obj.getName()

// 获取并访问字段（含私有字段，需 setAccessible）
Field field = clazz.getDeclaredField("age");
field.setAccessible(true);
int age = field.getInt(obj);
```

动态代理：JDK 动态代理基于接口（Proxy + InvocationHandler），CGLIB 基于继承（生成子类代理）。Spring AOP 默认对接口使用 JDK 代理、对普通类使用 CGLIB。

```java
interface Service { void doSomething(); }

class ServiceImpl implements Service {
    public void doSomething() { System.out.println("执行业务"); }
}

Service proxy = (Service) Proxy.newProxyInstance(
    Service.class.getClassLoader(),
    new Class[]{Service.class},
    (obj, method, args) -> {
        System.out.println("前置增强");
        Object result = method.invoke(new ServiceImpl(), args);
        System.out.println("后置增强");
        return result;
    }
);
proxy.doSomething();
```

注解：给代码附加元数据的机制。常用内置注解有 @Override（重写检查）、@Deprecated（标记废弃）、@SuppressWarnings（抑制警告）。自定义注解用 @interface 声明，配合元注解 @Retention（保留阶段）、@Target（作用位置）使用。注解本身不改变逻辑，由反射读取并处理。

```java
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
@interface MyAnnotation { String value(); }

class Demo {
    @MyAnnotation("测试")
    public void test() {}
}
```

## 10. Lambda 与 Stream API

函数式接口：只有一个抽象方法的接口，可用 @FunctionalInterface 标注。Java 内置常用函数式接口有 Consumer（消费）、Supplier（供给）、Function（转换）、Predicate（判断）。

```java
Consumer<String> print = s -> System.out.println(s);
Supplier<Double> random = () -> Math.random();
Function<Integer, String> toStr = n -> "数字:" + n;
Predicate<Integer> isPositive = n -> n > 0;
```

Lambda 表达式是函数式接口的简洁实现，语法为（参数）-> { 语句 }，可省略参数类型与单语句的 return 和花括号；方法引用（如 类::方法）是 Lambda 的更简洁写法。

Stream API 对集合做函数式操作，常用方法有 filter（过滤）、map（映射）、sorted（排序）、distinct（去重）、limit、reduce（归约）、collect（收集）。Stream 分为中间操作（惰性、返回 Stream）与终止操作（触发计算），且流只能消费一次；并行流 parallelStream 可并行处理，但要注意线程安全。

```java
List<String> names = Arrays.asList("Alice", "Bob", "Charlie", "David");
List<String> result = names.stream()
    .filter(n -> n.length() > 3)          // 中间操作：过滤
    .map(String::toUpperCase)             // 中间操作：映射
    .sorted()                             // 中间操作：排序
    .collect(Collectors.toList());        // 终止操作：收集
System.out.println(result);               // [ALICE, CHARLIE, DAVID]

int sum = IntStream.rangeClosed(1, 100).sum();   // 1 到 100 求和
```

## 11. IO 与序列化

字节流 vs 字符流：InputStream/OutputStream 处理字节（图片、视频等二进制），Reader/Writer 处理字符（文本）。字符流基于字节流加上编解码，读取文本优先用字符流；Buffered 包装类提供缓冲，减少磁盘 IO 次数。

```java
// 字节流写文件
try (FileOutputStream fos = new FileOutputStream("data.bin")) {
    fos.write(new byte[]{1, 2, 3});
}

// 字符流读文件
try (BufferedReader br = new BufferedReader(new FileReader("a.txt"))) {
    String line;
    while ((line = br.readLine()) != null) {
        System.out.println(line);
    }
}
```

BIO / NIO / AIO：BIO（阻塞 IO，一个连接一个线程，简单但并发能力差）、NIO（非阻塞 IO，基于 Channel + Buffer + Selector 多路复用，一个线程可管理多个连接）、AIO（异步 IO，通过回调处理完成事件）。

序列化：把对象转为字节流以便存储或网络传输，实现 java.io.Serializable 接口。transient 关键字修饰的字段不参与序列化；static 字段也不序列化；serialVersionUID 用于版本兼容，不一致会抛 InvalidClassException。

```java
class User implements Serializable {
    private static final long serialVersionUID = 1L;
    private String name;
    private transient String password;   // 不参与序列化
}

// 序列化
try (ObjectOutputStream oos = new ObjectOutputStream(new FileOutputStream("user.obj"))) {
    oos.writeObject(new User());
}
// 反序列化
try (ObjectInputStream ois = new ObjectInputStream(new FileInputStream("user.obj"))) {
    User user = (User) ois.readObject();
}
```

## 12. 常见设计模式（Java 实现）

单例模式：确保一个类只有一个实例。实现方式有饿汉式（类加载即创建，线程安全但可能浪费）、懒汉式（延迟创建，需处理线程安全）、双重检查锁（volatile + 两次判空）、静态内部类（利用类加载机制，推荐）、枚举（最简洁，天然防反射破坏）。

```java
// 双重检查锁
class Singleton {
    private static volatile Singleton instance;
    private Singleton() {}
    public static Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}

// 枚举单例
enum EnumSingleton {
    INSTANCE;
}
```

工厂模式：简单工厂（一个工厂根据参数生产不同产品，新增产品需改工厂代码）、工厂方法（每个产品对应一个工厂，符合开闭原则）、抽象工厂（生产一族相关产品）。

```java
interface Shape { void draw(); }
class Circle implements Shape { public void draw() { System.out.println("画圆"); } }
class Square implements Shape { public void draw() { System.out.println("画方"); } }

class ShapeFactory {
    public static Shape create(String type) {
        return switch (type) {
            case "circle" -> new Circle();
            case "square" -> new Square();
            default -> throw new IllegalArgumentException("未知类型");
        };
    }
}
```

代理模式：为对象提供代理以控制访问，分为静态代理与动态代理（JDK 动态代理 / CGLIB），常用于 AOP、日志、权限控制。

观察者模式：定义一对多依赖，主题状态变化时通知所有观察者（Java 中可用事件监听机制实现，如 GUI 按钮点击监听、消息订阅）。
