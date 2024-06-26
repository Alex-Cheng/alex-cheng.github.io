# 手撸一个C++迭代器

## 先撸一个简单版本
C++语言的特点就是少了一个符号都会造成非常不同的结果。以下代码有个很致命的错误，不知道能否一眼看出来。
```
// ranges_iterators.cpp : 此文件包含 "main" 函数。程序执行将在此处开始并结束。
//

#include <iostream>
#include <map>
#include <string>
#include <algorithm>
#include <iterator>

template <typename Rng, size_t I>
class elements_view
{
    using base_range = std::remove_reference_t<Rng>;
    using base_iterator = decltype(std::declval<Rng>().begin());

    using base_value_type = typename std::iterator_traits<base_iterator>::value_type;

public:
    class iterator {
    public:
        using difference_type = std::ptrdiff_t; // 迭代器是“高级”的指针，用起来应该跟指针相似，迭代器相减得到的结果的类型应该与指针相减得到的结果类型一样。
        using value_type = std::tuple_element_t<I, base_value_type>;
        using pointer = decltype(&std::get<I>(*std::declval<Rng>().begin())); // 是否与 value_type * 相等？
        using reference = decltype(std::get<I>(*std::declval<Rng>().begin())); // 是否与 value_type & 相等？
        using iterator_catalog = std::input_iterator_tag;

        iterator() = default;
        explicit iterator(const base_iterator& it) : it_(it) {}

        reference operator *() const { return std::get<I>(*it_); }
        pointer operator -> () const { return &std::get<I>(*it_); }

        iterator& operator ++() {
            ++it_;
            return *this;
        }

        iterator operator ++(int) {
            iterator temp{ *this };
            ++it_;
            return temp;
        }

        friend bool operator ==(const iterator& lhs, const iterator& rhs) {
            return lhs.it_ == rhs.it_;
        }

        friend bool operator !=(const iterator& lhs, const iterator& rhs) {
            return lhs.it_ != rhs.it_;
        }

    private:
        base_iterator it_{};
    };

    elements_view(Rng& rng) : rng_(&rng) {}

    iterator begin() const {
        // return iterator { rng_->begin() }
        auto iter = rng_->begin();
        return iterator{ iter };
    }
    iterator end() const {
        // return iterator{ rng_->end() };
        auto iter = rng_->end();
        return iterator{ iter };
    }

private:
    base_range* rng_{};
};

template <size_t I, typename Rng>
auto elements(Rng r) {
    return elements_view<Rng, I>(r);
}

int main()
{
    std::map<int, std::string> m{ {1,"aaa"}, {2, "bbb"} };
    auto v = elements<1>(m);
    //for (auto it = v.begin(); it != v.end(); ++it)
    //    std::cout << *it << '\n';
    auto out = std::ostream_iterator<std::string>(std::cout, ", ");
    std::copy(v.begin(), v.end(), out);

    std::cout << "Hello World!\n";
}
```

## 再撸一个可以跟ranges配合的版本
```C++
#include <iostream>
#include <map>
#include <string>
#include <algorithm>
#include <iterator>
#include <ranges>

namespace impl2 {

    template <typename Rng, size_t I>
    class elements_view
    {
        using base_range = Rng;
        using base_iterator = std::ranges::iterator_t<base_range>;
        using base_sentinel = std::ranges::sentinel_t<base_range>;
        using base_value_type = std::ranges::range_value_t<base_range>;

    public:
        class sentinel;
        class iterator {
        public:
            using difference_type = std::ptrdiff_t; // 迭代器是“高级”的指针，用起来应该跟指针相似，迭代器相减得到的结果的类型应该与指针相减得到的结果类型一样。
            using value_type = std::tuple_element_t<I, base_value_type>;
            using pointer = decltype(&std::get<I>(*std::declval<base_iterator>())); // 是否与 value_type * 相等？
            using reference = decltype(std::get<I>(*std::declval<base_iterator>())); // 是否与 value_type & 相等？
            using iterator_catalog = std::input_iterator_tag;

            iterator() = default;
            explicit iterator(const base_iterator& it) : it_(it) {}

            reference operator *() const { return std::get<I>(*it_); }
            pointer operator -> () const { return &std::get<I>(*it_); }

            iterator& operator ++() {
                ++it_;
                return *this;
            }

            iterator operator ++(int) {
                iterator temp{ *this };
                ++it_;
                return temp;
            }

            friend bool operator ==(const iterator&, const sentinel&);

            friend bool operator ==(const iterator& lhs, const iterator& rhs) {
                return lhs.it_ == rhs.it_;
            }

        private:
            base_iterator it_{};
        };

        class sentinel {
        public:
            sentinel() = default;
            explicit sentinel(base_sentinel iter) : iter_(iter) {}

            friend bool operator ==(const iterator& lhs, const sentinel& rhs) {
                return lhs.it_ == rhs.iter_;
            }

        private:
            base_sentinel iter_;
        };

        elements_view(Rng rng) : rng_(std::move(rng)) {}

        iterator begin() const { return iterator{ std::ranges::begin(rng_) }; }

		sentinel end() const { return sentinel{ std::ranges::end(rng_) }; }

    private:
        base_range rng_;
    };

    template <size_t I, typename Rng>
    auto elements(Rng&& r)
        requires std::ranges::view<std::remove_cvref_t<Rng>>
    {
        return elements_view<std::remove_cvref_t<Rng>, I>(std::forward<Rng>(r));
    }

    template <size_t I, typename Rng>
    auto elements(Rng&& r)
    {
        if constexpr (std::is_lvalue_reference_v<Rng>)
        {
            return elements<I>(std::views::all(std::forward<Rng>(r)));
        }
        else
        {
            return elements<I>(std::ranges::owning_view(std::forward<Rng>(r)));
        }
    }

}
```

