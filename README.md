TODO
---

- добавить линии отличные от центра

- выбор цели - игнорить базу врагов, если ещё не дошли до последней точки
- не стоять в точке респа (!!!!)
- ходить из стороны в сторону при атаке

- отступать от врагов опираясь на их радиус атаки
- не отступать, если уже дошли до базы врагов
- умное отступление с удержанием врагов в секторе обстрела (отступать задом вперёд)

- совмещать атаку и движение

```
если у нас мало хп или много врагов в радиусе ближней атаки - двигаемся к предыдущему вейпоинту {strafe_speed, turn, speed}'
иначе - двигаемся к базе врагов {strafe_speed, turn, speed}
есть враги в зоне действия каста - атакуем, крутимся к цели если не находимся в отступлении {turn, action, cast_angle, min_cast_distance}
```

- чтение сообщений и следование им

- usage bonuses
- add skills
- another attack cast
