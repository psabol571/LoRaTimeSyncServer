# Run dev server

```
docker-compose up --build
```

# Run migrations

```
docker-compose exec web python manage.py migrate
```

# Make migrations

```
docker-compose exec web python manage.py makemigrations
```